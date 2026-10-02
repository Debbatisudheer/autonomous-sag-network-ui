from __future__ import annotations

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.optimization.models import (
    ControlAction,
    ControlActionStatus,
    ControlActionType,
    ControlExecutionReport,
    ControlExecutionResult,
    ControlState,
    OptimizationPlan,
)


class AutonomousControlExecutor:
    """Apply optimized actions to the simulation-side control state and verify effects."""

    def apply(
        self,
        plan: OptimizationPlan,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
        state: ControlState | None = None,
    ) -> ControlExecutionReport:
        if plan.timestamp_s != network_snapshot.timestamp_s:
            raise ValueError("plan and network snapshots must have matching timestamps")
        if scheduling_snapshot is not None and scheduling_snapshot.timestamp_s != plan.timestamp_s:
            raise ValueError("scheduling and plan snapshots must have matching timestamps")

        current_state = state or ControlState.from_network_snapshot(network_snapshot)
        if current_state.timestamp_s > plan.timestamp_s:
            raise ValueError("control state timestamp cannot be newer than plan timestamp")

        next_state = current_state.model_copy(deep=True)
        next_state.timestamp_s = plan.timestamp_s
        next_state.version += 1
        results: list[ControlExecutionResult] = []

        for action in plan.selected_actions:
            if not action.feasible:
                results.append(
                    ControlExecutionResult(
                        action_id=action.action_id,
                        status=ControlActionStatus.REJECTED,
                        applied=False,
                        verified=False,
                        reason="action was not feasible",
                    )
                )
                continue
            applied, reason = self._apply_action(next_state, action)
            verified = applied and self._verify_action(
                next_state,
                action,
                network_snapshot=network_snapshot,
                scheduling_snapshot=scheduling_snapshot,
            )
            status = ControlActionStatus.VERIFIED if verified else ControlActionStatus.FAILED
            results.append(
                ControlExecutionResult(
                    action_id=action.action_id,
                    status=status,
                    applied=applied,
                    verified=verified,
                    reason=reason if verified else f"{reason}; verification failed",
                )
            )

        return ControlExecutionReport(
            timestamp_s=plan.timestamp_s,
            results=results,
            resulting_state=next_state,
            all_verified=all(item.verified for item in results) if results else True,
        )

    @staticmethod
    def _apply_action(state: ControlState, action: ControlAction) -> tuple[bool, str]:
        if action.action_type is ControlActionType.PREPARE_HANDOVER:
            if action.alternative_resource_id is None:
                return False, "handover target is missing"
            state.prepared_handover_targets[action.source_id] = action.alternative_resource_id
            return True, "handover preparation target recorded"

        if action.action_type is ControlActionType.RESERVE_SPECTRUM:
            resource_id = action.target_resource_id or action.alternative_resource_id
            if resource_id is None:
                return False, "spectrum reservation resource is missing"
            if resource_id not in state.reserved_resource_ids:
                state.reserved_resource_ids.append(resource_id)
            return True, "logical spectrum reservation recorded"

        if action.action_type is ControlActionType.REROUTE_FLOW:
            if action.alternative_resource_id is None:
                return False, "reroute target is missing"
            state.rerouted_sources[action.source_id] = action.alternative_resource_id
            state.selected_resources[action.source_id] = action.alternative_resource_id
            return True, "source rerouted to alternative resource"

        if action.action_type is ControlActionType.REDUCE_LOAD:
            state.load_reduction_ratios[action.source_id] = action.load_reduction_ratio
            return True, "configured load-reduction ratio recorded"

        if action.action_type is ControlActionType.PREPOSITION_RESOURCE:
            resource_id = action.alternative_resource_id or action.target_resource_id
            if resource_id is None:
                return False, "preposition resource is missing"
            if resource_id not in state.prepositioned_resource_ids:
                state.prepositioned_resource_ids.append(resource_id)
            return True, "resource prepositioning intent recorded"

        return True, "no control action required"

    @staticmethod
    def _verify_action(
        state: ControlState,
        action: ControlAction,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    ) -> bool:
        if action.action_type is ControlActionType.PREPARE_HANDOVER:
            return (
                state.prepared_handover_targets.get(action.source_id)
                == action.alternative_resource_id
            )
        if action.action_type is ControlActionType.RESERVE_SPECTRUM:
            resource_id = action.target_resource_id or action.alternative_resource_id
            if resource_id is None:
                return False
            if scheduling_snapshot is None:
                return resource_id in state.reserved_resource_ids
            return resource_id in state.reserved_resource_ids and any(
                item.resource_id == resource_id for item in scheduling_snapshot.utilization
            )
        if action.action_type is ControlActionType.REROUTE_FLOW:
            return state.selected_resources.get(action.source_id) == action.alternative_resource_id
        if action.action_type is ControlActionType.REDUCE_LOAD:
            return (
                state.load_reduction_ratios.get(action.source_id)
                == action.load_reduction_ratio
            )
        if action.action_type is ControlActionType.PREPOSITION_RESOURCE:
            resource_id = action.alternative_resource_id or action.target_resource_id
            if resource_id is None:
                return False
            return resource_id in state.prepositioned_resource_ids and any(
                candidate.resource_id == resource_id and candidate.available
                for association in network_snapshot.associations
                for candidate in association.candidates
            )
        return True


__all__ = ["AutonomousControlExecutor"]
