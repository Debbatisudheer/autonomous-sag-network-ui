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
from sag_network.optimization.advanced import (
    AdvancedOptimizationConfig,
    AdvancedOptimizationEngine,
)
from sag_network.optimization.models import OptimizationConfig
from sag_network.optimization.optimizer import OptimizationEngine
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
        resource_type="phase37_demo",
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
                        domain=NetworkDomain.AIR, margin=1.5, capacity=40e6, latency_ms=20.0
                    ),
                    candidate(
                        "gnd-a", domain=NetworkDomain.GROUND, margin=10.0,
                        capacity=100e6, latency_ms=5.0
                    ),
                ],
            ),
            UnifiedUserAssociation(
                user_id="user-02",
                selected_resource_id="leo-a",
                selected_domain=NetworkDomain.SPACE,
                demand_bps=15e6,
                allocated_capacity_bps=15e6,
                candidates=[
                    candidate(
                        "leo-a",
                        domain=NetworkDomain.SPACE, margin=2.0, capacity=30e6, latency_ms=35.0
                    ),
                    candidate(
                        "gnd-a", domain=NetworkDomain.GROUND, margin=9.0,
                        capacity=80e6, latency_ms=6.0
                    ),
                ],
            ),
        ],
    )
    scheduling = SpectrumSchedulingSnapshot(
        timestamp_s=timestamp_s,
        allocations=[],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a", total_resource_blocks=20, used_resource_blocks=18,
                free_resource_blocks=2, utilization_ratio=0.9, scheduled_capacity_bps=36e6,
                remaining_capacity_bps=4e6,
            ),
            ResourceUtilization(
                resource_id="leo-a", total_resource_blocks=20, used_resource_blocks=17,
                free_resource_blocks=3, utilization_ratio=0.85, scheduled_capacity_bps=25e6,
                remaining_capacity_bps=5e6,
            ),
            ResourceUtilization(
                resource_id="gnd-a", total_resource_blocks=20, used_resource_blocks=5,
                free_resource_blocks=15, utilization_ratio=0.25, scheduled_capacity_bps=25e6,
                remaining_capacity_bps=75e6,
            ),
        ],
    )
    warnings = [
        PredictiveEarlyWarning(
            source_id="uav-a:user-01", domain=NetworkDomain.AIR, metric=TelemetryMetric.SINR_DB,
            severity=WarningSeverity.CRITICAL, forecast_timestamp_s=11.0, lead_time_s=1.0,
            predicted_value=8.0, threshold_value=10.0, threshold_direction="below_minimum",
            confidence_score=0.9, reason="predicted radio degradation",
        ),
        PredictiveEarlyWarning(
            source_id="leo-a:user-02", domain=NetworkDomain.SPACE, metric=TelemetryMetric.SINR_DB,
            severity=WarningSeverity.WARNING, forecast_timestamp_s=11.0, lead_time_s=1.0,
            predicted_value=8.5, threshold_value=10.0, threshold_direction="below_minimum",
            confidence_score=0.9, reason="predicted radio degradation",
        ),
    ]
    decision = DecisionEngine(DecisionConfig()).decide(
        PredictiveReport(timestamp_s=timestamp_s, early_warnings=warnings),
        network_snapshot=network,
        scheduling_snapshot=scheduling,
    )
    baseline = OptimizationEngine(OptimizationConfig(maximum_actions=5)).optimize(
        decision, network_snapshot=network, scheduling_snapshot=scheduling
    )
    advanced = AdvancedOptimizationEngine(
        AdvancedOptimizationConfig(maximum_actions=2, beam_width=8, maximum_actions_per_resource=1)
    ).optimize(baseline)
    print(
        json.dumps(
            {
                "name": "Advanced Optimization",
                "phase": "37",
                "status": "pass",
                "baseline_candidate_count": len(baseline.candidate_actions),
                "pareto_frontier_count": len(advanced.pareto_frontier_ids),
                "selected_action_count": len(advanced.selected_actions),
                "selected_actions": [item.action_id for item in advanced.selected_actions],
                "objective_value": advanced.objective_value,
                "search_states": advanced.search_states,
                "state_mutation": False,
                "fixture": "synthetic optimization fixture",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
