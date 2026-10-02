from __future__ import annotations

from sag_network.decision.models import DecisionPriority
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.optimization.control import AutonomousControlExecutor
from sag_network.optimization.models import (
    ControlAction,
    ControlActionType,
    ControlState,
    OptimizationObjective,
    OptimizationPlan,
)
from sag_network.recovery.models import (
    FailureStatus,
    RecoveryAction,
    RecoveryActionType,
    RecoveryConfig,
    RecoveryExecutionResult,
    RecoveryPlan,
    SelfHealingState,
)


class SelfHealingExecutor:
    """Apply recovery actions to the existing simulation-side control plane and verify them."""

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        self.config = config or RecoveryConfig()
        self._control_executor = AutonomousControlExecutor()

    @staticmethod
    def _to_control_action(action: RecoveryAction) -> ControlAction | None:
        mapping = {
            RecoveryActionType.PREPARE_HANDOVER: ControlActionType.PREPARE_HANDOVER,
            RecoveryActionType.REROUTE_FLOW: ControlActionType.REROUTE_FLOW,
            RecoveryActionType.RESERVE_SPECTRUM: ControlActionType.RESERVE_SPECTRUM,
            RecoveryActionType.REDUCE_LOAD: ControlActionType.REDUCE_LOAD,
            RecoveryActionType.PREPOSITION_RESOURCE: ControlActionType.PREPOSITION_RESOURCE,
        }
        control_type = mapping.get(action.action_type)
        if control_type is None:
            return None
        return ControlAction(
            action_id=action.action_id,
            action_type=control_type,
            source_id=action.source_id,
            target_resource_id=action.target_resource_id,
            alternative_resource_id=action.alternative_resource_id,
            target_domain=action.target_domain,
            alternative_domain=action.alternative_domain,
            timestamp_s=action.timestamp_s,
            feasible=action.feasible,
            priority=DecisionPriority.CRITICAL,
            decision_utility=max(0.0, action.expected_recovery_score),
            expected_gain=max(0.0, action.expected_recovery_score),
            objective_score=max(0.0, action.expected_recovery_score),
            rationale=action.rationale,
        )

    def apply(
        self,
        plan: RecoveryPlan,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
        control_state: ControlState | None = None,
        state: SelfHealingState | None = None,
    ) -> tuple[list[RecoveryExecutionResult], SelfHealingState, ControlState | None]:
        if plan.timestamp_s != network_snapshot.timestamp_s:
            raise ValueError("recovery plan and network snapshots must have matching timestamps")
        if scheduling_snapshot is not None and scheduling_snapshot.timestamp_s != plan.timestamp_s:
            raise ValueError("scheduling and recovery plan snapshots must have matching timestamps")

        healing_state = (
            state or SelfHealingState(timestamp_s=plan.timestamp_s)
        ).model_copy(deep=True)
        healing_state.timestamp_s = plan.timestamp_s
        healing_state.version += 1
        for event_id in plan.event_ids:
            if event_id not in healing_state.active_event_ids:
                healing_state.active_event_ids.append(event_id)
            if event_id in healing_state.recovered_event_ids:
                healing_state.recovered_event_ids.remove(event_id)

        control = control_state.model_copy(deep=True) if control_state is not None else None
        results: list[RecoveryExecutionResult] = []
        eligible_actions: list[RecoveryAction] = []
        attempt_cycle_events: set[str] = set()

        for action in plan.selected_actions:
            previous_attempts = healing_state.attempt_counts.get(action.event_id, 0)
            if previous_attempts >= self.config.maximum_recovery_attempts:
                results.append(
                    RecoveryExecutionResult(
                        action_id=action.action_id,
                        status=FailureStatus.UNRECOVERABLE,
                        applied=False,
                        verified=False,
                        reason="maximum recovery attempts reached for failure event",
                    )
                )
                continue
            if action.event_id not in attempt_cycle_events:
                healing_state.attempt_counts[action.event_id] = previous_attempts + 1
                attempt_cycle_events.add(action.event_id)
            eligible_actions.append(action)

        control_actions = [
            converted
            for action in eligible_actions
            if (converted := self._to_control_action(action)) is not None
        ]
        if control_actions:
            control = control or ControlState.from_network_snapshot(network_snapshot)
            control_plan = OptimizationPlan(
                timestamp_s=plan.timestamp_s,
                objective=OptimizationObjective.BALANCED_UTILITY,
                objective_value=sum(action.objective_score for action in control_actions),
                candidate_actions=control_actions,
                selected_actions=control_actions,
            )
            control_report = self._control_executor.apply(
                control_plan,
                network_snapshot=network_snapshot,
                scheduling_snapshot=scheduling_snapshot,
                state=control,
            )
            control = control_report.resulting_state
            for action in eligible_actions:
                if action.action_type in {
                    RecoveryActionType.REFRESH_TELEMETRY,
                    RecoveryActionType.RELEASE_RESERVATION,
                }:
                    continue
                matching = next(
                    (item for item in control_report.results if item.action_id == action.action_id),
                    None,
                )
                if matching is None:
                    continue
                results.append(
                    RecoveryExecutionResult(
                        action_id=action.action_id,
                        status=FailureStatus.RECOVERED
                        if matching.verified
                        else FailureStatus.UNRECOVERABLE,
                        applied=matching.applied,
                        verified=matching.verified,
                        reason=matching.reason,
                    )
                )

        for action in eligible_actions:
            if action.action_type is RecoveryActionType.REFRESH_TELEMETRY:
                if action.source_id not in healing_state.refresh_requests:
                    healing_state.refresh_requests.append(action.source_id)
                results.append(
                    RecoveryExecutionResult(
                        action_id=action.action_id,
                        status=FailureStatus.RECOVERING,
                        applied=True,
                        verified=False,
                        reason=(
                            "telemetry refresh request recorded; fresh sample required "
                            "for verification"
                        ),
                    )
                )
            elif action.action_type is RecoveryActionType.RELEASE_RESERVATION:
                if control is None or action.target_resource_id is None:
                    results.append(
                        RecoveryExecutionResult(
                            action_id=action.action_id,
                            status=FailureStatus.UNRECOVERABLE,
                            applied=False,
                            verified=False,
                            reason=(
                                "reservation release requires a control state and target resource"
                            ),
                        )
                    )
                    continue
                resource_id = action.target_resource_id
                if resource_id in control.reserved_resource_ids:
                    control.reserved_resource_ids.remove(resource_id)
                verified = resource_id not in control.reserved_resource_ids
                results.append(
                    RecoveryExecutionResult(
                        action_id=action.action_id,
                        status=FailureStatus.RECOVERED if verified else FailureStatus.UNRECOVERABLE,
                        applied=True,
                        verified=verified,
                        reason="logical spectrum reservation released"
                        if verified
                        else "reservation remains present",
                    )
                )

        failed_action_ids = {result.action_id for result in results if not result.verified}
        active_event_ids = list(healing_state.active_event_ids)
        for event_id in plan.event_ids:
            event_action_ids = {
                action.action_id
                for action in plan.selected_actions
                if action.event_id == event_id
            }
            relevant_results = [
                result for result in results if result.action_id in event_action_ids
            ]
            if relevant_results and not any(
                result.action_id in failed_action_ids for result in relevant_results
            ):
                if event_id in active_event_ids:
                    active_event_ids.remove(event_id)
                if event_id not in healing_state.recovered_event_ids:
                    healing_state.recovered_event_ids.append(event_id)

        healing_state.active_event_ids = active_event_ids
        healing_state.refresh_requests = sorted(set(healing_state.refresh_requests))
        return results, healing_state, control


__all__ = ["SelfHealingExecutor"]
