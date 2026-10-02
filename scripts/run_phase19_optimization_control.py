from __future__ import annotations

import json

from sag_network.decision.engine import DecisionEngine
from sag_network.decision.models import DecisionConfig
from sag_network.domain.resource import ResourceUtilization, SpectrumSchedulingSnapshot
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.optimization.engine import AutonomousOptimizationEngine
from sag_network.optimization.models import OptimizationConfig
from sag_network.predictive.models import PredictiveEarlyWarning, PredictiveReport, WarningSeverity
from sag_network.telemetry.models import TelemetryMetric


def candidate(
    resource_id: str,
    *,
    domain: NetworkDomain,
    margin: float,
    capacity: float,
    latency_ms: float,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=domain,
        resource_type="phase19_demo",
        available=True,
        distance_m=1000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=margin + 5.0,
        link_margin_db=margin,
        shannon_capacity_bps=capacity,
        estimated_capacity_bps=capacity,
        propagation_delay_ms=latency_ms,
        doppler_shift_hz=0.0,
    )


def main() -> None:
    timestamp_s = 10.0
    network = UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20e6,
                allocated_capacity_bps=20e6,
                candidates=[
                    candidate(
                        "uav-a",
                        domain=NetworkDomain.AIR,
                        margin=1.5,
                        capacity=40e6,
                        latency_ms=20.0,
                    ),
                    candidate(
                        "gnd-a",
                        domain=NetworkDomain.GROUND,
                        margin=10.0,
                        capacity=100e6,
                        latency_ms=5.0,
                    ),
                ],
            )
        ],
    )
    scheduling = SpectrumSchedulingSnapshot(
        timestamp_s=timestamp_s,
        allocations=[],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a",
                total_resource_blocks=20,
                used_resource_blocks=18,
                free_resource_blocks=2,
                utilization_ratio=0.9,
                scheduled_capacity_bps=36e6,
                remaining_capacity_bps=4e6,
            ),
            ResourceUtilization(
                resource_id="gnd-a",
                total_resource_blocks=20,
                used_resource_blocks=5,
                free_resource_blocks=15,
                utilization_ratio=0.25,
                scheduled_capacity_bps=25e6,
                remaining_capacity_bps=75e6,
            ),
        ],
    )
    warning = PredictiveEarlyWarning(
        source_id="uav-a:user-01",
        domain=NetworkDomain.AIR,
        metric=TelemetryMetric.SINR_DB,
        severity=WarningSeverity.CRITICAL,
        forecast_timestamp_s=11.0,
        lead_time_s=1.0,
        predicted_value=8.0,
        threshold_value=10.0,
        threshold_direction="below_minimum",
        confidence_score=0.9,
        reason="predicted radio degradation",
    )
    decision = DecisionEngine(DecisionConfig()).decide(
        PredictiveReport(timestamp_s=timestamp_s, early_warnings=[warning]),
        network_snapshot=network,
        scheduling_snapshot=scheduling,
    )
    report = AutonomousOptimizationEngine(
        OptimizationConfig(maximum_actions=3)
    ).run(
        decision,
        network_snapshot=network,
        scheduling_snapshot=scheduling,
    )
    print(
        json.dumps(
            {
                "timestamp_s": report.timestamp_s,
                "objective": report.plan.objective.value,
                "candidate_actions": [
                    {
                        "action_id": item.action_id,
                        "action": item.action_type.value,
                        "source": item.source_id,
                        "target": item.target_resource_id,
                        "alternative": item.alternative_resource_id,
                        "feasible": item.feasible,
                        "expected_gain": item.expected_gain,
                        "objective_score": item.objective_score,
                    }
                    for item in report.plan.candidate_actions
                ],
                "selected_actions": [
                    {
                        "action_id": item.action_id,
                        "action": item.action_type.value,
                        "alternative": item.alternative_resource_id,
                        "objective_score": item.objective_score,
                    }
                    for item in report.plan.selected_actions
                ],
                "execution": [item.model_dump(mode="json") for item in report.execution.results],
                "all_verified": report.execution.all_verified,
                "control_state": report.execution.resulting_state.model_dump(mode="json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
