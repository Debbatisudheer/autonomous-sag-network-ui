from __future__ import annotations

import hashlib

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedCandidate, UnifiedNetworkSnapshot
from sag_network.recovery.models import (
    FailureDiagnosis,
    FailureEvent,
    FailureType,
    RecoveryAction,
    RecoveryActionType,
    RecoveryConfig,
    RecoveryPlan,
)


def _action_id(
    timestamp_s: float,
    event_id: str,
    action_type: RecoveryActionType,
    target: str,
    source_id: str = "",
) -> str:
    payload = f"{timestamp_s:.6f}|{event_id}|{action_type.value}|{target}|{source_id}"
    return f"recovery-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


class RecoveryPlanner:
    """Builds bounded recovery plans from diagnosed faults and current candidate state."""

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        self.config = config or RecoveryConfig()

    @staticmethod
    def _associations_for_event(
        snapshot: UnifiedNetworkSnapshot,
        event: FailureEvent,
    ) -> list[tuple[str, list[UnifiedCandidate]]]:
        if ":" in event.source_id:
            user_id = event.source_id.split(":", 1)[-1]
            return [
                (association.user_id, association.candidates)
                for association in snapshot.associations
                if association.user_id == user_id
            ]
        if event.resource_id is not None:
            return [
                (association.user_id, association.candidates)
                for association in snapshot.associations
                if association.selected_resource_id == event.resource_id
            ]
        return [
            (association.user_id, association.candidates)
            for association in snapshot.associations
            if association.user_id == event.source_id
        ]

    def _best_alternative(
        self,
        candidates: list[UnifiedCandidate],
        *,
        failed_resource_id: str | None,
    ) -> UnifiedCandidate | None:
        options = [
            candidate
            for candidate in candidates
            if candidate.available
            and candidate.resource_id != failed_resource_id
            and candidate.link_margin_db >= self.config.minimum_alternative_margin_db
            and candidate.estimated_capacity_bps >= self.config.minimum_alternative_capacity_bps
        ]
        return max(
            options,
            key=lambda item: (
                item.link_margin_db,
                item.estimated_capacity_bps,
                -item.propagation_delay_ms,
                item.resource_id,
            ),
            default=None,
        )

    def _candidate_for_action(
        self,
        diagnosis: FailureDiagnosis,
        event: FailureEvent,
        user_id: str,
        candidates: list[UnifiedCandidate],
        snapshot: UnifiedNetworkSnapshot,
    ) -> RecoveryAction:
        _ = diagnosis
        failed_resource_id = event.resource_id
        alternative = self._best_alternative(candidates, failed_resource_id=failed_resource_id)

        if event.failure_type is FailureType.TELEMETRY_STALE:
            action_type = RecoveryActionType.REFRESH_TELEMETRY
            return RecoveryAction(
                event_id=event.event_id,
                action_id=_action_id(
                    snapshot.timestamp_s,
                    event.event_id,
                    action_type,
                    event.source_id,
                    event.source_id,
                ),
                action_type=action_type,
                source_id=event.source_id,
                timestamp_s=snapshot.timestamp_s,
                feasible=True,
                expected_recovery_score=1.0,
                rationale="request a fresh telemetry sample before further autonomous actuation",
            )

        if event.failure_type is FailureType.RESOURCE_EXHAUSTION:
            action_type = RecoveryActionType.REDUCE_LOAD
            return RecoveryAction(
                event_id=event.event_id,
                action_id=_action_id(
                    snapshot.timestamp_s,
                    event.event_id,
                    action_type,
                    event.source_id,
                    event.source_id,
                ),
                action_type=action_type,
                source_id=event.source_id,
                target_resource_id=event.resource_id,
                timestamp_s=snapshot.timestamp_s,
                feasible=True,
                expected_recovery_score=self.config.load_reduction_ratio,
                rationale="reduce offered load while the exhausted resource recovers",
            )

        if alternative is not None:
            source_id = user_id
            action_type = RecoveryActionType.REROUTE_FLOW
            return RecoveryAction(
                event_id=event.event_id,
                action_id=_action_id(
                    snapshot.timestamp_s,
                    event.event_id,
                    action_type,
                    alternative.resource_id,
                    source_id,
                ),
                action_type=action_type,
                source_id=source_id,
                target_resource_id=failed_resource_id,
                alternative_resource_id=alternative.resource_id,
                target_domain=event.domain,
                alternative_domain=alternative.domain,
                timestamp_s=snapshot.timestamp_s,
                feasible=True,
                expected_recovery_score=max(0.0, alternative.link_margin_db)
                + alternative.estimated_capacity_bps / 1_000_000.0,
                rationale=(
                    f"alternate resource {alternative.resource_id} is available with "
                    f"{alternative.link_margin_db:.2f} dB margin and "
                    f"{alternative.estimated_capacity_bps:.0f} bps estimated capacity"
                ),
            )

        action_type = RecoveryActionType.REFRESH_TELEMETRY
        return RecoveryAction(
            event_id=event.event_id,
            action_id=_action_id(
                snapshot.timestamp_s,
                event.event_id,
                action_type,
                event.source_id,
                event.source_id,
            ),
            action_type=action_type,
            source_id=event.source_id,
            timestamp_s=snapshot.timestamp_s,
            feasible=False,
            expected_recovery_score=0.0,
            rationale="no safe deterministic recovery action is available from the current state",
            constraints=["no available alternative resource meets configured recovery thresholds"],
        )

    def plan(
        self,
        events: list[FailureEvent],
        diagnoses: list[FailureDiagnosis],
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
    ) -> RecoveryPlan:
        if (
            scheduling_snapshot is not None
            and scheduling_snapshot.timestamp_s != network_snapshot.timestamp_s
        ):
            raise ValueError("scheduling and network snapshots must have matching timestamps")

        diagnosis_map = {item.event_id: item for item in diagnoses}
        actions: list[RecoveryAction] = []
        unresolved: list[str] = []
        for event in events:
            diagnosis = diagnosis_map.get(event.event_id)
            if diagnosis is None:
                unresolved.append(event.event_id)
                continue
            associations = self._associations_for_event(network_snapshot, event)
            if not associations:
                action = self._candidate_for_action(
                    diagnosis, event, event.source_id, [], network_snapshot
                )
                actions.append(action)
                unresolved.append(event.event_id)
                continue
            for user_id, candidates in associations:
                action = self._candidate_for_action(
                    diagnosis, event, user_id, candidates, network_snapshot
                )
                actions.append(action)
                if not action.feasible:
                    unresolved.append(event.event_id)

        feasible = [action for action in actions if action.feasible]
        selected = sorted(
            feasible,
            key=lambda action: (
                action.expected_recovery_score,
                action.action_type.value,
                action.source_id,
            ),
            reverse=True,
        )[: self.config.maximum_recovery_actions]
        selected_event_ids = {action.event_id for action in selected}
        for action in feasible:
            if action.event_id not in selected_event_ids and action.event_id not in unresolved:
                unresolved.append(action.event_id)

        return RecoveryPlan(
            timestamp_s=network_snapshot.timestamp_s,
            event_ids=[event.event_id for event in events],
            candidate_actions=actions,
            selected_actions=selected,
            unresolved_event_ids=sorted(set(unresolved)),
        )


__all__ = ["RecoveryPlanner"]
