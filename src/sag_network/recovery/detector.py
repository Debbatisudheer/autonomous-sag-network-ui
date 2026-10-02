from __future__ import annotations

import hashlib

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import NetworkDomain, UnifiedNetworkSnapshot
from sag_network.optimization.models import OptimizationReport
from sag_network.recovery.models import (
    FailureEvent,
    FailureEvidence,
    FailureSeverity,
    FailureType,
    RecoveryConfig,
)
from sag_network.telemetry.models import RealTimeStateSnapshot, TelemetryMetric, TelemetryQuality


def _event_id(_timestamp_s: float, failure_type: FailureType, source_id: str, detail: str) -> str:
    payload = f"{failure_type.value}|{source_id}|{detail}"
    return f"failure-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _domain_for_candidate(
    snapshot: UnifiedNetworkSnapshot, resource_id: str
) -> NetworkDomain | None:
    for association in snapshot.associations:
        for candidate in association.candidates:
            if candidate.resource_id == resource_id:
                return candidate.domain
    return None


def _selected_resource_is_unavailable(
    snapshot: UnifiedNetworkSnapshot,
) -> list[tuple[str, str, NetworkDomain]]:
    failures: list[tuple[str, str, NetworkDomain]] = []
    for association in snapshot.associations:
        resource_id = association.selected_resource_id
        if resource_id is None:
            continue
        candidate = next(
            (item for item in association.candidates if item.resource_id == resource_id),
            None,
        )
        if candidate is not None and not candidate.available:
            failures.append((association.user_id, resource_id, candidate.domain))
    return failures


def _resource_failures(snapshot: UnifiedNetworkSnapshot) -> list[tuple[str, NetworkDomain]]:
    resources: dict[str, list[bool]] = {}
    domains: dict[str, NetworkDomain] = {}
    for association in snapshot.associations:
        for candidate in association.candidates:
            resources.setdefault(candidate.resource_id, []).append(candidate.available)
            domains[candidate.resource_id] = candidate.domain
    return [
        (resource_id, domains[resource_id])
        for resource_id, availability in sorted(resources.items())
        if len(availability) >= 2 and not any(availability)
    ]


class FailureDetector:
    """Deterministically detects hard failures from real-time and planning state."""

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        self.config = config or RecoveryConfig()

    def detect(
        self,
        *,
        telemetry_state: RealTimeStateSnapshot,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
        optimization_report: OptimizationReport | None = None,
    ) -> list[FailureEvent]:
        if telemetry_state.timestamp_s != network_snapshot.timestamp_s:
            raise ValueError("telemetry and network snapshots must have matching timestamps")
        if (
            scheduling_snapshot is not None
            and scheduling_snapshot.timestamp_s != network_snapshot.timestamp_s
        ):
            raise ValueError("scheduling and network snapshots must have matching timestamps")
        if (
            optimization_report is not None
            and optimization_report.timestamp_s != network_snapshot.timestamp_s
        ):
            raise ValueError("optimization and network snapshots must have matching timestamps")

        events: list[FailureEvent] = []
        node_failed_resources = {
            resource_id for resource_id, _ in _resource_failures(network_snapshot)
        }

        stale_samples = [sample for sample in telemetry_state.samples if sample.stale]
        if len(stale_samples) >= self.config.stale_sample_limit:
            for sample in stale_samples:
                events.append(
                    FailureEvent(
                        event_id=_event_id(
                            network_snapshot.timestamp_s,
                            FailureType.TELEMETRY_STALE,
                            sample.source_id,
                            sample.metric.value,
                        ),
                        failure_type=FailureType.TELEMETRY_STALE,
                        source_id=sample.source_id,
                        domain=sample.domain,
                        timestamp_s=network_snapshot.timestamp_s,
                        severity=FailureSeverity.WARNING,
                        confidence_score=1.0,
                        symptoms=[f"{sample.metric.value} telemetry is stale"],
                        evidence=[
                            FailureEvidence(
                                source_id=sample.source_id,
                                domain=sample.domain,
                                metric=sample.metric.value,
                                observed_value=sample.value,
                                timestamp_s=sample.timestamp_s,
                                age_s=sample.age_s,
                                details="latest accepted telemetry sample exceeded stale threshold",
                            )
                        ],
                    )
                )

        for sample in telemetry_state.samples:
            if sample.quality is TelemetryQuality.INVALID:
                continue
            if sample.stale:
                continue
            if sample.metric is TelemetryMetric.AVAILABLE and sample.value <= 0:
                resource_id = sample.source_id.split(":", 1)[0]
                if resource_id in node_failed_resources:
                    continue
                domain = sample.domain
                failure_type = FailureType.LINK_FAILURE
                resource_id = sample.source_id.split(":", 1)[0]
                events.append(
                    FailureEvent(
                        event_id=_event_id(
                            network_snapshot.timestamp_s,
                            failure_type,
                            sample.source_id,
                            "available=0",
                        ),
                        failure_type=failure_type,
                        source_id=sample.source_id,
                        resource_id=resource_id,
                        domain=domain,
                        timestamp_s=network_snapshot.timestamp_s,
                        severity=FailureSeverity.CRITICAL,
                        confidence_score=1.0,
                        symptoms=["telemetry reports link unavailable"],
                        evidence=[
                            FailureEvidence(
                                source_id=sample.source_id,
                                domain=domain,
                                metric=sample.metric.value,
                                observed_value=sample.value,
                                threshold_value=1.0,
                                timestamp_s=sample.timestamp_s,
                                age_s=sample.age_s,
                                details="availability metric is zero",
                            )
                        ],
                    )
                )

        for user_id, resource_id, domain in _selected_resource_is_unavailable(network_snapshot):
            if resource_id in node_failed_resources:
                continue
            events.append(
                FailureEvent(
                    event_id=_event_id(
                        network_snapshot.timestamp_s,
                        FailureType.LINK_FAILURE,
                        f"{resource_id}:{user_id}",
                        "selected_resource_unavailable",
                    ),
                    failure_type=FailureType.LINK_FAILURE,
                    source_id=f"{resource_id}:{user_id}",
                    resource_id=resource_id,
                    domain=domain,
                    timestamp_s=network_snapshot.timestamp_s,
                    severity=FailureSeverity.CRITICAL,
                    confidence_score=1.0,
                    symptoms=["selected access resource is unavailable"],
                    evidence=[
                        FailureEvidence(
                            source_id=f"{resource_id}:{user_id}",
                            domain=domain,
                            metric="candidate.available",
                            observed_value=0.0,
                            threshold_value=1.0,
                            timestamp_s=network_snapshot.timestamp_s,
                            details="selected resource candidate is unavailable",
                        )
                    ],
                )
            )

        for resource_id, domain in _resource_failures(network_snapshot):
            events.append(
                FailureEvent(
                    event_id=_event_id(
                        network_snapshot.timestamp_s,
                        FailureType.NODE_FAILURE,
                        resource_id,
                        "all_candidates_unavailable",
                    ),
                    failure_type=FailureType.NODE_FAILURE,
                    source_id=resource_id,
                    resource_id=resource_id,
                    domain=domain,
                    timestamp_s=network_snapshot.timestamp_s,
                    severity=FailureSeverity.CRITICAL,
                    confidence_score=1.0,
                    symptoms=["all observed user links to resource are unavailable"],
                    evidence=[
                        FailureEvidence(
                            source_id=resource_id,
                            domain=domain,
                            metric="candidate.available",
                            observed_value=0.0,
                            threshold_value=1.0,
                            timestamp_s=network_snapshot.timestamp_s,
                            details="no available candidate exists for the resource",
                        )
                    ],
                )
            )

        if scheduling_snapshot is not None:
            for item in scheduling_snapshot.utilization:
                if item.utilization_ratio >= self.config.maximum_resource_utilization_ratio:
                    events.append(
                        FailureEvent(
                            event_id=_event_id(
                                scheduling_snapshot.timestamp_s,
                                FailureType.RESOURCE_EXHAUSTION,
                                item.resource_id,
                                "utilization",
                            ),
                            failure_type=FailureType.RESOURCE_EXHAUSTION,
                            source_id=item.resource_id,
                            resource_id=item.resource_id,
                            domain=_domain_for_candidate(network_snapshot, item.resource_id),
                            timestamp_s=network_snapshot.timestamp_s,
                            severity=FailureSeverity.CRITICAL,
                            confidence_score=1.0,
                            symptoms=["spectrum utilization reached recovery threshold"],
                            evidence=[
                                FailureEvidence(
                                    source_id=item.resource_id,
                                    domain=_domain_for_candidate(
                                        network_snapshot, item.resource_id
                                    ),
                                    metric="resource_utilization_ratio",
                                    observed_value=item.utilization_ratio,
                                    threshold_value=self.config.maximum_resource_utilization_ratio,
                                    timestamp_s=scheduling_snapshot.timestamp_s,
                                    details=(
                                        "resource utilization exceeds configured recovery boundary"
                                    ),
                                )
                            ],
                        )
                    )
                elif item.remaining_capacity_bps <= self.config.minimum_remaining_capacity_bps:
                    events.append(
                        FailureEvent(
                            event_id=_event_id(
                                scheduling_snapshot.timestamp_s,
                                FailureType.CAPACITY_EXHAUSTION,
                                item.resource_id,
                                "remaining_capacity",
                            ),
                            failure_type=FailureType.CAPACITY_EXHAUSTION,
                            source_id=item.resource_id,
                            resource_id=item.resource_id,
                            domain=_domain_for_candidate(network_snapshot, item.resource_id),
                            timestamp_s=network_snapshot.timestamp_s,
                            severity=FailureSeverity.WARNING,
                            confidence_score=1.0,
                            symptoms=["resource has insufficient remaining capacity"],
                            evidence=[
                                FailureEvidence(
                                    source_id=item.resource_id,
                                    domain=_domain_for_candidate(
                                        network_snapshot, item.resource_id
                                    ),
                                    metric="resource_remaining_capacity_bps",
                                    observed_value=item.remaining_capacity_bps,
                                    threshold_value=self.config.minimum_remaining_capacity_bps,
                                    timestamp_s=scheduling_snapshot.timestamp_s,
                                    details=(
                                        "remaining scheduled capacity is at or below "
                                        "configured boundary"
                                    ),
                                )
                            ],
                        )
                    )

        if optimization_report is not None:
            by_action_id = {
                action.action_id: action
                for action in optimization_report.plan.selected_actions
            }
            for result in optimization_report.execution.results:
                if result.verified:
                    continue
                action = by_action_id.get(result.action_id)
                if action is None:
                    continue
                failure_type = (
                    FailureType.HANDOVER_FAILURE
                    if action.action_type.value == "prepare_handover"
                    else FailureType.ROUTE_FAILURE
                    if action.action_type.value == "reroute_flow"
                    else FailureType.UNKNOWN
                )
                if failure_type is FailureType.UNKNOWN:
                    continue
                events.append(
                    FailureEvent(
                        event_id=_event_id(
                            network_snapshot.timestamp_s,
                            failure_type,
                            action.source_id,
                            result.action_id,
                        ),
                        failure_type=failure_type,
                        source_id=action.source_id,
                        resource_id=action.target_resource_id,
                        domain=action.target_domain,
                        timestamp_s=network_snapshot.timestamp_s,
                        severity=FailureSeverity.CRITICAL,
                        confidence_score=1.0,
                        symptoms=[result.reason],
                        evidence=[
                            FailureEvidence(
                                source_id=action.source_id,
                                domain=action.target_domain,
                                metric="control_execution",
                                timestamp_s=network_snapshot.timestamp_s,
                                details="previous optimization control action was not verified",
                            )
                        ],
                    )
                )

        return self._deduplicate(events)

    @staticmethod
    def _deduplicate(events: list[FailureEvent]) -> list[FailureEvent]:
        unique: dict[str, FailureEvent] = {}
        for event in events:
            unique[event.event_id] = event
        return [unique[key] for key in sorted(unique)]


__all__ = ["FailureDetector"]
