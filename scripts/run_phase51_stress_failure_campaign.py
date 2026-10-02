from __future__ import annotations

import json

from sag_network.stress import FailureMode, FailureSeverity, StressFailureCampaign, StressScenario


def scenarios() -> list[StressScenario]:
    return [
        StressScenario(
            scenario_id="packet-loss-critical",
            failure_mode=FailureMode.PACKET_LOSS,
            baseline_value=0.01,
            stressed_value=0.35,
            recovered_value=0.01,
            warning_threshold=0.10,
            critical_threshold=0.25,
            higher_is_worse=True,
            expected_severity=FailureSeverity.CRITICAL,
        ),
        StressScenario(
            scenario_id="latency-warning",
            failure_mode=FailureMode.LATENCY_SPIKE,
            baseline_value=20.0,
            stressed_value=75.0,
            recovered_value=20.0,
            warning_threshold=50.0,
            critical_threshold=100.0,
            higher_is_worse=True,
            expected_severity=FailureSeverity.WARNING,
        ),
        StressScenario(
            scenario_id="node-outage-critical",
            failure_mode=FailureMode.NODE_OUTAGE,
            baseline_value=1.0,
            stressed_value=0.0,
            recovered_value=1.0,
            warning_threshold=0.5,
            critical_threshold=0.0,
            higher_is_worse=False,
            expected_severity=FailureSeverity.CRITICAL,
        ),
        StressScenario(
            scenario_id="resource-overload-warning",
            failure_mode=FailureMode.RESOURCE_OVERLOAD,
            baseline_value=0.62,
            stressed_value=0.84,
            recovered_value=0.62,
            warning_threshold=0.80,
            critical_threshold=0.95,
            higher_is_worse=True,
            expected_severity=FailureSeverity.WARNING,
        ),
        StressScenario(
            scenario_id="recovery-baseline",
            failure_mode=FailureMode.RESOURCE_OVERLOAD,
            baseline_value=0.62,
            stressed_value=0.62,
            recovered_value=0.62,
            warning_threshold=0.80,
            critical_threshold=0.95,
            higher_is_worse=True,
            expected_severity=FailureSeverity.NONE,
        ),
    ]


def main() -> None:
    result = StressFailureCampaign().run(
        scenarios(),
        campaign_id="phase51-sag-stress-failure-campaign",
        fixture="synthetic offline stress-and-failure fixture",
    )
    print(
        json.dumps(
            {
                "name": "Stress & Failure Campaign",
                "phase": "51",
                "status": "pass",
                "campaign_id": result.campaign_id,
                "scenario_count": result.scenario_count,
                "finding_count": result.finding_count,
                "critical_count": result.critical_count,
                "warning_count": result.warning_count,
                "passed_count": result.passed_count,
                "findings": [item.model_dump(mode="json") for item in result.findings],
                "campaign_fingerprint": result.campaign_fingerprint,
                "network_mutation": False,
                "fixture": result.fixture,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
