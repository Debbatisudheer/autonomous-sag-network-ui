from __future__ import annotations

import pytest

from sag_network.closed_loop_autonomy import (
    AutonomyAction,
    ClosedLoopAutonomyConfig,
    ClosedLoopAutonomyEngine,
)
from sag_network.cross_domain_sag import CrossDomainSAGEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryQuality, TelemetryRecord


def _records(count: int = 4) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"autonomy-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="autonomy-test",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=4.0 + index,
            unit="ms",
        )
        for index in range(count)
    ]


def _config(**overrides: object) -> ClosedLoopAutonomyConfig:
    values: dict[str, object] = {
        "timestamps_s": [0.0, 15.0, 60.0],
        "user_demand_bps": {
            "sag-user-01": 10e6,
            "sag-user-02": 10e6,
            "sag-user-03": 10e6,
        },
        "timeout_s": 1.0,
    }
    values.update(overrides)
    return ClosedLoopAutonomyConfig(**values)


def test_closed_loop_is_deterministic() -> None:
    engine = ClosedLoopAutonomyEngine()
    left = engine.run(
        _records(),
        config=_config(),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    right = engine.run(
        _records(),
        config=_config(),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.summary.cycle_count == 9
    assert left.summary.verification_fail_count == 0


def test_closed_loop_observe_decide_act_verify_contains_transition() -> None:
    report = ClosedLoopAutonomyEngine().run(
        _records(),
        config=_config(
            timestamps_s=[0.0, 120.0, 240.0, 360.0, 600.0, 1200.0, 2400.0]
        ),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.summary.handover_count >= 1
    assert report.summary.attach_count >= 1
    assert report.summary.verification_fail_count == 0
    assert any(cycle.decision_action is AutonomyAction.HANDOVER for cycle in report.cycles)


def test_closed_loop_rejects_descending_timestamps() -> None:
    with pytest.raises(ValueError, match="non-decreasing"):
        ClosedLoopAutonomyConfig(
            timestamps_s=[1.0, 0.0],
            timeout_s=1.0,
        )


def test_closed_loop_telemetry_gate_blocks_state_changes() -> None:
    records = _records(2)
    records[1] = records[1].model_copy(update={"quality": TelemetryQuality.INVALID})
    report = ClosedLoopAutonomyEngine().run(
        records,
        config=_config(minimum_telemetry_health=0.75),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.telemetry_loop.accepted_record_count == 1
    assert report.telemetry_loop.received_record_count == 2
    assert report.summary.blocked_count > 0
    assert all(cycle.decision_action is AutonomyAction.BLOCKED for cycle in report.cycles)
    assert report.summary.verification_fail_count == 0
