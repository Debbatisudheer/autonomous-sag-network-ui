from __future__ import annotations

from collections.abc import Iterable

from sag_network.recovery.models import (
    FailureDiagnosis,
    FailureEvent,
    FailureType,
    RecoveryActionType,
    RootCause,
)


class FailureDiagnoser:
    """Maps detected events to deterministic root causes and recovery action classes."""

    def diagnose(self, events: Iterable[FailureEvent]) -> list[FailureDiagnosis]:
        diagnoses: list[FailureDiagnosis] = []
        for event in events:
            if event.failure_type is FailureType.NODE_FAILURE:
                root_cause = RootCause.RESOURCE_UNAVAILABLE
                actions = [
                    RecoveryActionType.PREPARE_HANDOVER,
                    RecoveryActionType.REROUTE_FLOW,
                    RecoveryActionType.PREPOSITION_RESOURCE,
                ]
                rationale = (
                    "resource-level unavailability is consistent with a node/resource failure"
                )
            elif event.failure_type is FailureType.LINK_FAILURE:
                root_cause = RootCause.LINK_QUALITY_DEGRADED
                actions = [
                    RecoveryActionType.PREPARE_HANDOVER,
                    RecoveryActionType.REROUTE_FLOW,
                    RecoveryActionType.REDUCE_LOAD,
                ]
                rationale = (
                    "the selected or observed link is unavailable and an alternate path "
                    "should be considered"
                )
            elif event.failure_type in {
                FailureType.RESOURCE_EXHAUSTION,
                FailureType.CAPACITY_EXHAUSTION,
            }:
                root_cause = RootCause.RESOURCE_EXHAUSTED
                actions = [
                    RecoveryActionType.RESERVE_SPECTRUM,
                    RecoveryActionType.REDUCE_LOAD,
                    RecoveryActionType.REROUTE_FLOW,
                ]
                rationale = (
                    "resource occupancy or remaining capacity has crossed the recovery boundary"
                )
            elif event.failure_type is FailureType.TELEMETRY_STALE:
                root_cause = RootCause.TELEMETRY_STALE
                actions = [RecoveryActionType.REFRESH_TELEMETRY]
                rationale = (
                    "recovery should first restore a current observation before changing "
                    "network state"
                )
            elif event.failure_type in {
                FailureType.HANDOVER_FAILURE,
                FailureType.ROUTE_FAILURE,
            }:
                root_cause = (
                    RootCause.CONTROL_ACTION_FAILED
                    if event.failure_type is FailureType.HANDOVER_FAILURE
                    else RootCause.ROUTE_UNAVAILABLE
                )
                actions = [
                    RecoveryActionType.REROUTE_FLOW,
                    RecoveryActionType.PREPARE_HANDOVER,
                    RecoveryActionType.PREPOSITION_RESOURCE,
                ]
                rationale = (
                    "a previous control action was not verified, so an alternate recovery "
                    "path is required"
                )
            else:
                root_cause = RootCause.UNKNOWN
                actions = [RecoveryActionType.REFRESH_TELEMETRY]
                rationale = "the event has no deterministic specialized recovery mapping"

            diagnoses.append(
                FailureDiagnosis(
                    event_id=event.event_id,
                    source_id=event.source_id,
                    root_cause=root_cause,
                    confidence_score=event.confidence_score,
                    contributing_symptoms=event.symptoms.copy(),
                    recommended_action_types=actions,
                    rationale=rationale,
                )
            )
        return diagnoses


__all__ = ["FailureDiagnoser"]
