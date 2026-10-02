from __future__ import annotations

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.hardware_edge import (
    EdgeWorkloadSpec,
    HardwareEdgeDeploymentEngine,
    HardwareEdgeEvidence,
    synthetic_device_profile,
)
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"r-{index}",
            timestamp_s=10.0 + index,
            sequence=index,
            source_id="edge-a",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=10.0 + index,
            unit="ms",
        )
        for index in range(8)
    ]


def workload(**overrides: object) -> EdgeWorkloadSpec:
    values: dict[str, object] = {
        "workload_id": "summary",
        "max_cpu_time_ms": 50.0,
        "max_python_heap_kb": 512,
        "max_wall_time_ms": 100.0,
        "maximum_input_records": 128,
    }
    values.update(overrides)
    return EdgeWorkloadSpec(**values)


def test_synthetic_deployment_completes_within_budget() -> None:
    report = HardwareEdgeDeploymentEngine().deploy(
        records(),
        device=synthetic_device_profile(),
        workload=workload(),
        evidence_class=HardwareEdgeEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.workload.accepted is True
    assert report.workload.completed is True
    assert report.telemetry_summary.input_record_count == 8
    assert report.network_mutation is False


def test_deployment_is_deterministic_at_output_level() -> None:
    engine = HardwareEdgeDeploymentEngine()
    first = engine.deploy(
        records(),
        device=synthetic_device_profile(),
        workload=workload(),
        evidence_class=HardwareEdgeEvidence.SYNTHETIC_FIXTURE,
    )
    second = engine.deploy(
        records(),
        device=synthetic_device_profile(),
        workload=workload(),
        evidence_class=HardwareEdgeEvidence.SYNTHETIC_FIXTURE,
    )
    assert first.telemetry_summary == second.telemetry_summary
    assert first.workload.output_fingerprint == second.workload.output_fingerprint
    assert first.deployment_fingerprint == second.deployment_fingerprint


def test_input_record_limit_is_enforced() -> None:
    with pytest.raises(ValueError, match="maximum_input_records"):
        HardwareEdgeDeploymentEngine().deploy(
            records(),
            device=synthetic_device_profile(),
            workload=workload(maximum_input_records=4),
            evidence_class=HardwareEdgeEvidence.SYNTHETIC_FIXTURE,
        )


def test_tight_wall_budget_produces_degraded_execution() -> None:
    report = HardwareEdgeDeploymentEngine().deploy(
        records(),
        device=synthetic_device_profile(),
        workload=workload(max_wall_time_ms=0.000001),
        evidence_class=HardwareEdgeEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.workload.completed is True
    assert report.workload.accepted is False
    assert report.workload.within_wall_budget is False
