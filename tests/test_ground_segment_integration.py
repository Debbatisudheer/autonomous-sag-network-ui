from sag_network.ground_segment import (
    GroundSegmentConfig,
    GroundSegmentEvidence,
    GroundSegmentIntegrationEngine,
)
from sag_network.network_telemetry_loop import NetworkLoopEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"r-{index}",
            timestamp_s=100.0 + index,
            sequence=index,
            source_id="ground-source",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=10.0 + index,
            unit="ms",
        )
        for index in range(8)
    ]


def config(*, udp: bool = False) -> GroundSegmentConfig:
    return GroundSegmentConfig(
        reference_time_s=107.0,
        user_demand_bps={
            "ground-user-01": 5e6,
            "ground-user-02": 5e6,
        },
        use_udp_loopback=udp,
        timeout_s=1.0,
    )


def test_synthetic_ground_segment_integrates_telemetry_and_ground_network() -> None:
    report = GroundSegmentIntegrationEngine().run(
        records(),
        config=config(),
        evidence_class=GroundSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.status == "pass"
    assert report.telemetry_loop.accepted_record_count == 8
    assert report.summary.telemetry_sample_count == 1
    assert report.summary.associated_user_count == 2
    assert report.summary.unassociated_user_count == 0
    assert report.summary.total_allocated_capacity_bps == 10e6
    assert report.external_network_used is False
    assert report.network_mutation is False


def test_udp_ground_segment_uses_local_network_evidence() -> None:
    report = GroundSegmentIntegrationEngine().run(
        records(),
        config=config(udp=True),
        evidence_class=GroundSegmentEvidence.LOCAL_NETWORK_TEST,
    )
    assert report.telemetry_loop.evidence_class is NetworkLoopEvidence.LOCAL_NETWORK_TEST
    assert report.telemetry_loop.received_record_count == 8
    assert report.telemetry_loop.delivered_record_rate == 1.0
    assert report.telemetry_loop.external_network_used is False


def test_ground_segment_is_deterministic() -> None:
    first = GroundSegmentIntegrationEngine().run(
        records(),
        config=config(),
        evidence_class=GroundSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    second = GroundSegmentIntegrationEngine().run(
        records(),
        config=config(),
        evidence_class=GroundSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    assert first.integration_fingerprint == second.integration_fingerprint
