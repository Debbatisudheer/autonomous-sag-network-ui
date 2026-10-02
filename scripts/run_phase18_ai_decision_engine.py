from __future__ import annotations

import json

from sag_network.decision.engine import DecisionEngine
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.predictive.models import PredictiveEarlyWarning, PredictiveReport, WarningSeverity
from sag_network.telemetry.models import TelemetryMetric


def main() -> None:
    network = UnifiedNetworkSnapshot(
        timestamp_s=10.0,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20_000_000.0,
                allocated_capacity_bps=20_000_000.0,
                candidates=[
                    UnifiedCandidate(
                        resource_id="uav-a",
                        domain=NetworkDomain.AIR,
                        resource_type="uav",
                        available=True,
                        distance_m=1000.0,
                        rx_power_dbm=-70.0,
                        noise_power_dbm=-100.0,
                        sinr_db=6.0,
                        link_margin_db=1.0,
                        shannon_capacity_bps=50_000_000.0,
                        estimated_capacity_bps=40_000_000.0,
                        propagation_delay_ms=4.0,
                        doppler_shift_hz=1200.0,
                    ),
                    UnifiedCandidate(
                        resource_id="gnd-a",
                        domain=NetworkDomain.GROUND,
                        resource_type="ground-cell",
                        available=True,
                        distance_m=1500.0,
                        rx_power_dbm=-62.0,
                        noise_power_dbm=-100.0,
                        sinr_db=18.0,
                        link_margin_db=9.0,
                        shannon_capacity_bps=120_000_000.0,
                        estimated_capacity_bps=100_000_000.0,
                        propagation_delay_ms=6.0,
                        doppler_shift_hz=0.0,
                    ),
                ],
            )
        ],
    )
    predictive = PredictiveReport(
        timestamp_s=10.0,
        early_warnings=[
            PredictiveEarlyWarning(
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
                reason="predicted sinr_db below minimum threshold within 1.000s",
            )
        ],
    )

    report = DecisionEngine().decide(predictive, network_snapshot=network)
    print(
        json.dumps(
            {
                "timestamp_s": report.timestamp_s,
                "status": report.status.value,
                "warning_count": report.predictive_warning_count,
                "candidate_actions": [
                    {
                        "action": action.action_type.value,
                        "target": action.target_resource_id,
                        "alternative": action.alternative_resource_id,
                        "feasible": action.feasible,
                        "utility": round(action.utility_score, 4),
                        "priority": action.priority.value,
                    }
                    for action in report.candidate_actions
                ],
                "selected_decisions": [
                    {
                        "decision_id": decision.decision_id,
                        "action": decision.action.action_type.value,
                        "target": decision.action.target_resource_id,
                        "alternative": decision.action.alternative_resource_id,
                        "confidence": decision.confidence_score,
                        "explanation": decision.explanation,
                    }
                    for decision in report.selected_decisions
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
