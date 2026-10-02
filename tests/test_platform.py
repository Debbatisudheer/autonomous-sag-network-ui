from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.domain.unified import NetworkDomain
from sag_network.edge.models import (
    EdgeCapability,
    EdgeFabricSnapshot,
    EdgeNode,
    EdgeNodeHealth,
    EdgeNodeType,
)
from sag_network.platform.engine import AutonomousSAGPlatform
from sag_network.platform.models import (
    AutonomousPlatformConfig,
    PlatformCycleInput,
    PlatformStage,
    PlatformStatus,
)
from sag_network.validation.models import ValidationScenarioConfig
from sag_network.validation.scenario import (
    build_network_snapshot,
    build_scenario,
    build_telemetry_records,
)


def _fabric(timestamp_s: float) -> EdgeFabricSnapshot:
    capabilities = list(EdgeCapability)
    node_types = [
        ("air-edge-a", EdgeNodeType.AIR_EDGE, NetworkDomain.AIR),
        ("ground-edge-a", EdgeNodeType.GROUND_EDGE, NetworkDomain.GROUND),
        ("regional-controller", EdgeNodeType.REGIONAL_CONTROLLER, None),
        ("central-controller", EdgeNodeType.CENTRAL_CONTROLLER, None),
    ]
    return EdgeFabricSnapshot(
        timestamp_s=timestamp_s,
        nodes=[
            EdgeNode(
                node_id=node_id,
                node_type=node_type,
                domain=domain,
                capabilities=capabilities,
                cpu_capacity_millicores=20_000,
                memory_capacity_mb=16_384,
                queue_capacity=100,
                processing_latency_ms=1.0,
                network_latency_ms=5.0,
                health=EdgeNodeHealth.ONLINE,
                active=True,
            )
            for node_id, node_type, domain in node_types
        ],
    )


def _cycle(timestamp_s: float = 40.0, fault_fraction: float = 0.2) -> PlatformCycleInput:
    cfg = ValidationScenarioConfig(
        scenario_id=f"test-{int(timestamp_s)}",
        user_count=10,
        fault_fraction=fault_fraction,
        timestamp_s=timestamp_s,
        telemetry_points=4,
    )
    scenario = build_scenario(cfg)
    return PlatformCycleInput(
        timestamp_s=timestamp_s,
        network_snapshot=build_network_snapshot(scenario),
        failure_network_snapshot=build_network_snapshot(scenario, failed=True),
        telemetry_records=build_telemetry_records(scenario),
        edge_fabric=_fabric(timestamp_s),
        source_ids=(
            [f"uav-a:{uid}" for uid in scenario.fault_user_ids]
            or ["uav-a:user-0001"]
        ),
    )


def test_platform_runs_all_stages() -> None:
    platform = AutonomousSAGPlatform(AutonomousPlatformConfig(platform_id="test-platform"))
    report = platform.run_cycle(_cycle())
    assert report.status is PlatformStatus.PASS
    assert [stage.stage for stage in report.stages] == list(PlatformStage)
    assert report.telemetry_record_count == 40
    assert report.predictive_warning_count == 10
    assert report.decision_count == 10
    assert report.control_action_count == 10
    assert report.verified_control_action_count == 10
    assert report.detected_failure_count == 2
    assert report.recovered_failure_count == 2
    assert report.completed_distributed_task_count == report.distributed_task_count
    assert report.distributed_state_converged
    assert report.message_delivered == 1


def test_platform_state_persists_between_cycles() -> None:
    platform = AutonomousSAGPlatform(AutonomousPlatformConfig(platform_id="test-platform"))
    first = platform.run_cycle(_cycle(40.0, 0.0))
    second = platform.run_cycle(_cycle(50.0, 0.0))
    assert first.twin_snapshot_id == "snapshot-0001"
    assert second.twin_snapshot_id == "snapshot-0002"
    assert platform.cycle_count == 2
    assert platform.latest_twin_snapshot is not None
    assert platform.latest_twin_snapshot.timestamp_s == 50.0
    assert platform.latest_control_state is not None


def test_platform_rejects_non_monotonic_cycles() -> None:
    platform = AutonomousSAGPlatform(AutonomousPlatformConfig(platform_id="test-platform"))
    platform.run_cycle(_cycle(40.0, 0.0))
    with pytest.raises(ValueError, match="timestamps must increase strictly"):
        platform.run_cycle(_cycle(40.0, 0.0))


def test_cycle_input_rejects_timestamp_mismatch() -> None:
    cfg = ValidationScenarioConfig(scenario_id="bad", user_count=1, timestamp_s=40.0)
    scenario = build_scenario(cfg)
    with pytest.raises(ValidationError):
        PlatformCycleInput(
            timestamp_s=50.0,
            network_snapshot=build_network_snapshot(scenario),
            telemetry_records=build_telemetry_records(scenario),
            edge_fabric=_fabric(50.0),
        )


def test_platform_fingerprint_is_deterministic_for_same_inputs() -> None:
    input_cycle = _cycle(40.0, 0.0)
    first = AutonomousSAGPlatform(
        AutonomousPlatformConfig(platform_id="test-platform")
    ).run_cycle(input_cycle)
    second = AutonomousSAGPlatform(
        AutonomousPlatformConfig(platform_id="test-platform")
    ).run_cycle(input_cycle)
    assert first.deterministic_fingerprint == second.deterministic_fingerprint


def test_platform_exposes_twin_and_control_state() -> None:
    platform = AutonomousSAGPlatform(AutonomousPlatformConfig(platform_id="test-platform"))
    report = platform.run_cycle(_cycle())
    assert platform.latest_twin_snapshot is not None
    assert platform.latest_twin_snapshot.snapshot_id == report.twin_snapshot_id
    assert platform.latest_control_state is not None
    assert platform.latest_healing_state is not None


def test_platform_source_ids_limit_distributed_workload() -> None:
    cycle = _cycle(40.0, 0.0).model_copy(update={"source_ids": ["uav-a:user-0001"]})
    report = AutonomousSAGPlatform(
        AutonomousPlatformConfig(platform_id="test-platform")
    ).run_cycle(cycle)
    assert report.distributed_task_count == 7


def test_platform_handles_no_faults() -> None:
    report = AutonomousSAGPlatform(AutonomousPlatformConfig(platform_id="test-platform")).run_cycle(
        _cycle(40.0, 0.0)
    )
    assert report.detected_failure_count == 0
    assert report.recovered_failure_count == 0
    assert report.status is PlatformStatus.PASS
