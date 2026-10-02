from sag_network.domain.unified import NetworkDomain
from sag_network.network_telemetry_loop import (
    NetworkLoopEvidence,
    NetworkTelemetryLoopEngine,
    SyntheticTelemetryLoopTransport,
)
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def make_records(count: int = 8) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"r-{index}",
            timestamp_s=100.0 + index,
            sequence=index,
            source_id="ground-01",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=10.0 + index,
            unit="ms",
        )
        for index in range(count)
    ]


def test_synthetic_loop_delivers_records() -> None:
    report = NetworkTelemetryLoopEngine().run(
        make_records(),
        reference_time_s=200.0,
        transport=SyntheticTelemetryLoopTransport(),
        evidence_class=NetworkLoopEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.status == "pass"
    assert report.received_record_count == 8
    assert report.accepted_record_count == 8
    assert report.state_sample_count == 1
    assert report.external_network_used is False
    assert report.network_mutation is False


def test_udp_loopback_is_local_and_deterministic() -> None:
    records = make_records(4)
    engine = NetworkTelemetryLoopEngine()
    first = engine.run_udp_loopback(
        records,
        reference_time_s=200.0,
        evidence_class=NetworkLoopEvidence.LOCAL_NETWORK_TEST,
    )
    second = engine.run_udp_loopback(
        records,
        reference_time_s=200.0,
        evidence_class=NetworkLoopEvidence.LOCAL_NETWORK_TEST,
    )
    assert first.received_record_count == 4
    assert first.accepted_record_count == 4
    assert first.external_network_used is False
    assert first.network_mutation is False
    assert first.loop_fingerprint == second.loop_fingerprint
