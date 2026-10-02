from __future__ import annotations

from sag_network.domain.unified import NetworkDomain
from sag_network.hardware_sdr_closed_loop import (
    HardwareSdrClosedLoopConfig,
    HardwareSdrClosedLoopEngine,
    HardwareSdrClosedLoopEvidence,
)
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"p72-{index}",
            timestamp_s=72.0 + index,
            sequence=index,
            source_id="ground-edge-01",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=10.0 + index * 0.25,
            unit="ms",
        )
        for index in range(8)
    ]


def config() -> HardwareSdrClosedLoopConfig:
    return HardwareSdrClosedLoopConfig(
        sample_rate_hz=2_000_000.0,
        center_frequency_hz=915_000_000.0,
        symbol_rate_hz=100_000.0,
        amplitude=0.8,
        decision_threshold=0.5,
        sample_count=4096,
        timeout_us=100_000,
        source_id="ground-node-01",
        destination_id="air-node-01",
    )


def test_synthetic_closed_loop_completes() -> None:
    report = HardwareSdrClosedLoopEngine().run_synthetic(
        records(), config=config(), timestamp_s=72.0
    )
    assert report.evidence_class is HardwareSdrClosedLoopEvidence.SYNTHETIC_FIXTURE
    assert report.edge.workload.accepted is True
    assert report.wireless_link.delivered is True
    assert report.wireless_link.crc_valid is True
    assert report.hardware_sdr_used is False
    assert report.network_mutation is False


def test_synthetic_closed_loop_is_deterministic() -> None:
    engine = HardwareSdrClosedLoopEngine()
    first = engine.run_synthetic(records(), config=config(), timestamp_s=72.0)
    second = engine.run_synthetic(records(), config=config(), timestamp_s=72.0)
    assert first.sdr.sample_fingerprint == second.sdr.sample_fingerprint
    assert first.wireless_link.link_fingerprint == second.wireless_link.link_fingerprint
    assert first.loop_fingerprint == second.loop_fingerprint


def test_local_host_uses_local_edge_but_synthetic_sdr() -> None:
    report = HardwareSdrClosedLoopEngine().run_local_host(
        records(), config=config(), timestamp_s=72.0
    )
    assert report.evidence_class is HardwareSdrClosedLoopEvidence.LOCAL_HOST_MEASUREMENT
    assert report.edge.evidence_class.value == "LOCAL HOST MEASUREMENT"
    assert report.sdr.external_hardware_used is False
    assert report.wireless_link.delivered is True


def test_control_payload_is_bounded() -> None:
    report = HardwareSdrClosedLoopEngine().run_synthetic(
        records(), config=config(), timestamp_s=72.0
    )
    assert len(report.wireless_link.link_fingerprint) == 64
    assert len(report.control_payload_sha256) == 64


def test_public_data_evidence_is_preserved() -> None:
    report = HardwareSdrClosedLoopEngine().run_synthetic(
        records(), config=config(), timestamp_s=72.0, public_data=True
    )
    assert report.evidence_class is HardwareSdrClosedLoopEvidence.PUBLIC_DATA
    assert report.sdr.external_hardware_used is False
    assert report.wireless_link.delivered is True
