from __future__ import annotations

from sag_network.air_segment import (
    AirSegmentConfig,
    AirSegmentEvidence,
    AirSegmentIntegrationEngine,
)
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"test-{index}",
            timestamp_s=400.0 + index,
            sequence=index,
            source_id="air-test",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.LATENCY_MS,
            value=12.0 + index,
            unit="ms",
        )
        for index in range(8)
    ]


def config(use_udp_loopback: bool = False) -> AirSegmentConfig:
    return AirSegmentConfig(
        reference_time_s=407.0,
        user_demand_bps={
            "air-user-01": 10e6,
            "air-user-02": 10e6,
            "air-user-03": 10e6,
        },
        use_udp_loopback=use_udp_loopback,
        timeout_s=1.0,
    )


def test_synthetic_air_segment_integration_passes() -> None:
    report = AirSegmentIntegrationEngine().run(
        records(),
        config=config(),
        evidence_class=AirSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.status == "pass"
    assert len(report.air_snapshot.associations) == 3
    assert report.summary.associated_user_count == 3
    assert report.summary.telemetry_sample_count >= 1
    assert report.network_mutation is False


def test_udp_loopback_integration_passes() -> None:
    report = AirSegmentIntegrationEngine().run(
        records(),
        config=config(True),
        evidence_class=AirSegmentEvidence.LOCAL_NETWORK_TEST,
    )
    assert report.status == "pass"
    assert report.telemetry_loop.transport == "udp-loopback"
    assert report.telemetry_loop.external_network_used is False


def test_air_association_is_deterministic() -> None:
    engine = AirSegmentIntegrationEngine()
    first = engine.run(
        records(),
        config=config(),
        evidence_class=AirSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    second = engine.run(
        records(),
        config=config(),
        evidence_class=AirSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    assert first.air_snapshot.model_dump() == second.air_snapshot.model_dump()
