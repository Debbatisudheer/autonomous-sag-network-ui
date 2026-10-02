from __future__ import annotations

import json

from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.recovery.engine import FailureRecoveryEngine
from sag_network.telemetry.models import (
    RealTimeStateSnapshot,
    TelemetryMetric,
    TelemetryQuality,
    TelemetryStateSample,
)


def candidate(
    resource_id: str,
    *,
    domain: NetworkDomain,
    available: bool,
    margin_db: float,
    capacity_bps: float,
    latency_ms: float,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=domain,
        resource_type="phase20_demo",
        available=available,
        distance_m=10_000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=margin_db + 5.0,
        link_margin_db=margin_db,
        shannon_capacity_bps=capacity_bps,
        estimated_capacity_bps=capacity_bps,
        propagation_delay_ms=latency_ms,
        doppler_shift_hz=0.0,
    )


def main() -> None:
    timestamp_s = 20.0
    network = UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=30e6,
                allocated_capacity_bps=30e6,
                candidates=[
                    candidate(
                        "uav-a",
                        domain=NetworkDomain.AIR,
                        available=False,
                        margin_db=-5.0,
                        capacity_bps=0.0,
                        latency_ms=25.0,
                    ),
                    candidate(
                        "gnd-a",
                        domain=NetworkDomain.GROUND,
                        available=True,
                        margin_db=12.0,
                        capacity_bps=120e6,
                        latency_ms=5.0,
                    ),
                ],
            ),
            UnifiedUserAssociation(
                user_id="user-02",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20e6,
                allocated_capacity_bps=20e6,
                candidates=[
                    candidate(
                        "uav-a",
                        domain=NetworkDomain.AIR,
                        available=False,
                        margin_db=-5.0,
                        capacity_bps=0.0,
                        latency_ms=25.0,
                    ),
                    candidate(
                        "gnd-a",
                        domain=NetworkDomain.GROUND,
                        available=True,
                        margin_db=10.0,
                        capacity_bps=100e6,
                        latency_ms=6.0,
                    ),
                ],
            ),
        ],
    )
    telemetry = RealTimeStateSnapshot(
        timestamp_s=timestamp_s,
        samples=[
            TelemetryStateSample(
                source_id="uav-a:user-01",
                domain=NetworkDomain.AIR,
                metric=TelemetryMetric.AVAILABLE,
                value=0.0,
                unit="bool",
                timestamp_s=timestamp_s,
                sequence=20,
                age_s=0.0,
                quality=TelemetryQuality.GOOD,
                stale=False,
            ),
            TelemetryStateSample(
                source_id="uav-a:user-02",
                domain=NetworkDomain.AIR,
                metric=TelemetryMetric.AVAILABLE,
                value=0.0,
                unit="bool",
                timestamp_s=timestamp_s,
                sequence=20,
                age_s=0.0,
                quality=TelemetryQuality.GOOD,
                stale=False,
            ),
        ],
    )

    report = FailureRecoveryEngine().run(
        telemetry_state=telemetry,
        network_snapshot=network,
    )
    print(
        json.dumps(
            {
                "timestamp_s": report.timestamp_s,
                "detected_failures": [
                    {
                        "event_id": event.event_id,
                        "type": event.failure_type.value,
                        "source": event.source_id,
                        "resource": event.resource_id,
                        "severity": event.severity.value,
                    }
                    for event in report.detected_failures
                ],
                "diagnoses": [
                    {
                        "event_id": item.event_id,
                        "root_cause": item.root_cause.value,
                        "recommended_actions": [
                            action.value for action in item.recommended_action_types
                        ],
                    }
                    for item in report.diagnoses
                ],
                "selected_recovery_actions": [
                    {
                        "event_id": action.event_id,
                        "action": action.action_type.value,
                        "source": action.source_id,
                        "alternative": action.alternative_resource_id,
                        "verified": action.feasible,
                    }
                    for action in report.plan.selected_actions
                ],
                "execution": [item.model_dump(mode="json") for item in report.execution_results],
                "all_recovered": report.all_recovered,
                "self_healing_state": report.self_healing_state.model_dump(mode="json"),
                "resulting_control_state": (
                    report.resulting_control_state.model_dump(mode="json")
                    if report.resulting_control_state is not None
                    else None
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
