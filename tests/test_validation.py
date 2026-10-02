from __future__ import annotations

from sag_network.validation.models import ValidationScenarioConfig, ValidationStatus
from sag_network.validation.runner import (
    default_validation_matrix,
    run_scenario,
    run_validation_matrix,
)
from sag_network.validation.scenario import (
    build_network_snapshot,
    build_scenario,
    build_telemetry_records,
)


def test_scenario_generation_is_deterministic() -> None:
    config = ValidationScenarioConfig(scenario_id="test", user_count=10, fault_fraction=0.2)
    first = build_scenario(config)
    second = build_scenario(config)
    assert first == second
    assert first.fault_user_ids == ["user-0001", "user-0002"]
    assert first.candidate_count == 30


def test_network_snapshot_scale_and_fault_injection() -> None:
    scenario = build_scenario(
        ValidationScenarioConfig(scenario_id="fault", user_count=6, fault_fraction=0.5)
    )
    healthy = build_network_snapshot(scenario)
    failed = build_network_snapshot(scenario, failed=True)
    assert len(healthy.associations) == 6
    unavailable = [
        candidate
        for association in failed.associations
        for candidate in association.candidates
        if candidate.resource_id == "uav-a" and not candidate.available
    ]
    assert len(unavailable) == 3


def test_telemetry_history_is_bounded_by_requested_count() -> None:
    scenario = build_scenario(
        ValidationScenarioConfig(scenario_id="telemetry", user_count=4, telemetry_points=5)
    )
    records = build_telemetry_records(scenario)
    assert len(records) == 20
    assert records[0].value > records[4].value


def test_single_validation_scenario_passes() -> None:
    result = run_scenario(
        ValidationScenarioConfig(scenario_id="single", user_count=10, fault_fraction=0.2)
    )
    assert result.status is ValidationStatus.PASS
    assert result.predictive_warnings == 10
    assert result.detected_failures >= 1
    assert result.recovery_success_ratio == 1.0
    assert result.placement_success_ratio == 1.0
    assert result.distributed_state_converged
    assert result.message_delivered == 1


def test_validation_matrix_contains_scale_scenarios() -> None:
    matrix = default_validation_matrix()
    assert [config.user_count for config in matrix] == [10, 50, 100, 250, 500]


def test_validation_matrix_is_deterministic_except_runtime() -> None:
    configs = [
        ValidationScenarioConfig(scenario_id="a", user_count=5),
        ValidationScenarioConfig(scenario_id="b", user_count=8, fault_fraction=0.25),
    ]
    first = run_validation_matrix(configs)
    second = run_validation_matrix(configs)
    assert first.deterministic_matrix_fingerprint == second.deterministic_matrix_fingerprint
    assert first.status is ValidationStatus.PASS
