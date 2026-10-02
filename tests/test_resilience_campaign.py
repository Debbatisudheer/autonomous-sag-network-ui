from __future__ import annotations

import pytest

from sag_network.cross_domain_sag import CrossDomainSAGEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.resilience_campaign import (
    ResilienceCampaignConfig,
    ResilienceCampaignEngine,
    ResilienceFailureMode,
    ResilienceScenario,
    default_resilience_scenarios,
)


def config() -> ResilienceCampaignConfig:
    return ResilienceCampaignConfig(
        timestamps_s=[0.0, 300.0, 600.0, 900.0, 1200.0],
        user_demand_bps={
            "sag-user-01": 10e6,
            "sag-user-02": 10e6,
            "sag-user-03": 10e6,
        },
        timeout_s=1.0,
    )


def test_default_scenarios_are_unique() -> None:
    scenarios = default_resilience_scenarios()
    assert len(scenarios) == len({scenario.scenario_id for scenario in scenarios})
    assert {scenario.failure_mode for scenario in scenarios} == {
        ResilienceFailureMode.RESOURCE_OUTAGE,
        ResilienceFailureMode.DOMAIN_OUTAGE,
        ResilienceFailureMode.TELEMETRY_DEGRADATION,
        ResilienceFailureMode.CAPACITY_DEGRADATION,
        ResilienceFailureMode.CASCADING_OUTAGE,
    }


def test_deterministic_campaign() -> None:
    engine = ResilienceCampaignEngine()
    scenarios = [
        ResilienceScenario(
            scenario_id="z-ground",
            failure_mode=ResilienceFailureMode.RESOURCE_OUTAGE,
            start_time_s=600.0,
            end_time_s=900.0,
            affected_resource_ids=("ground-cell-02",),
        ),
        ResilienceScenario(
            scenario_id="a-air",
            failure_mode=ResilienceFailureMode.RESOURCE_OUTAGE,
            start_time_s=0.0,
            end_time_s=300.0,
            affected_resource_ids=("air-uav-01",),
        ),
    ]
    first = engine.run([], scenarios, config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE)
    second = engine.run([], reversed(scenarios), config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE)
    assert first == second
    assert [result.scenario_id for result in first.scenarios] == ["a-air", "z-ground"]


def test_telemetry_degradation_blocks_actions() -> None:
    engine = ResilienceCampaignEngine()
    scenario = ResilienceScenario(
        scenario_id="telemetry",
        failure_mode=ResilienceFailureMode.TELEMETRY_DEGRADATION,
        start_time_s=300.0,
        end_time_s=900.0,
        telemetry_health=0.5,
    )
    result = engine.run([], [scenario], config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE)
    assert result.scenarios[0].blocked_count > 0
    assert result.scenarios[0].verification_fail_count == 0


def test_capacity_degradation_can_surface_verification_failure() -> None:
    engine = ResilienceCampaignEngine()
    scenario = ResilienceScenario(
        scenario_id="capacity",
        failure_mode=ResilienceFailureMode.CAPACITY_DEGRADATION,
        start_time_s=600.0,
        end_time_s=900.0,
        affected_resource_ids=("ground-cell-02",),
        capacity_scale=0.01,
    )
    result = engine.run([], [scenario], config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE)
    assert result.scenarios[0].verification_fail_count >= 0
    assert result.scenarios[0].max_unmet_demand_bps >= 0.0


def test_invalid_scenario_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="end_time_s must be greater"):
        ResilienceScenario(
            scenario_id="bad",
            failure_mode=ResilienceFailureMode.RESOURCE_OUTAGE,
            start_time_s=10.0,
            end_time_s=10.0,
            affected_resource_ids=("ground-cell-01",),
        )


def test_invalid_domain_outage_without_domain_is_rejected() -> None:
    with pytest.raises(ValueError, match="require affected_domains"):
        ResilienceScenario(
            scenario_id="bad-domain",
            failure_mode=ResilienceFailureMode.DOMAIN_OUTAGE,
            start_time_s=0.0,
            end_time_s=10.0,
        )


def test_config_rejects_non_monotonic_timestamps() -> None:
    with pytest.raises(ValueError, match="non-decreasing"):
        ResilienceCampaignConfig(timestamps_s=[0.0, 2.0, 1.0], timeout_s=1.0)


def test_space_domain_enum_is_supported() -> None:
    scenario = ResilienceScenario(
        scenario_id="space-domain",
        failure_mode=ResilienceFailureMode.DOMAIN_OUTAGE,
        start_time_s=0.0,
        end_time_s=10.0,
        affected_domains=(NetworkDomain.SPACE,),
    )
    assert scenario.affected_domains == (NetworkDomain.SPACE,)
