from __future__ import annotations

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.fusion import fuse_telemetry, FusionConfig
from sag_network.telemetry import (
    TelemetryMetric,
    TelemetryQuality,
    TelemetryRecord,
)


def _record(
    record_id: str,
    timestamp_s: float,
    value: float,
    source: str,
) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=0,
        source_id="sat-01",
        domain=NetworkDomain.SPACE,
        metric=TelemetryMetric.SINR_DB,
        value=value,
        unit="dB",
        quality=TelemetryQuality.GOOD,
        metadata={
            "provenance_source": source,
            "provenance_sha256": f"sha-{source}",
        },
    )


def test_fuses_two_independent_provenance_sources() -> None:
    report = fuse_telemetry(
        [
            _record("a", 10.0, 20.0, "OPS-SAT"),
            _record("b", 10.5, 22.0, "SatNOGS"),
        ],
        config=FusionConfig(timestamp_tolerance_s=1.0),
    )

    assert report.input_record_count == 2
    assert report.provenance_source_count == 2
    assert report.fused_record_count == 1
    assert report.unresolved_record_count == 0
    assert report.conflict_count == 1
    assert report.fused[0].value == pytest.approx(21.0)
    assert report.fused[0].spread == pytest.approx(2.0)
    assert report.fused[0].source_names == ("OPS-SAT", "SatNOGS")


def test_does_not_fuse_outside_time_tolerance() -> None:
    report = fuse_telemetry(
        [
            _record("a", 10.0, 20.0, "OPS-SAT"),
            _record("b", 12.0, 22.0, "SatNOGS"),
        ],
        config=FusionConfig(timestamp_tolerance_s=0.5),
    )

    assert report.fused_record_count == 0
    assert report.unresolved_record_count == 2


def test_fingerprint_is_deterministic() -> None:
    records = [
        _record("b", 10.5, 22.0, "SatNOGS"),
        _record("a", 10.0, 20.0, "OPS-SAT"),
    ]
    first = fuse_telemetry(records)
    second = fuse_telemetry(list(reversed(records)))

    assert first == second
    assert first.fingerprint


def test_invalid_quality_propagates() -> None:
    record = _record("a", 10.0, 20.0, "OPS-SAT")
    record = record.model_copy(update={"quality": TelemetryQuality.INVALID})
    other = _record("b", 10.0, 22.0, "SatNOGS")

    report = fuse_telemetry([record, other])

    assert report.fused[0].quality is TelemetryQuality.INVALID


def test_incompatible_units_remain_unresolved() -> None:
    first = _record("a", 10.0, 20.0, "OPS-SAT")
    second = _record("b", 10.0, 22.0, "SatNOGS").model_copy(
        update={"unit": "dBm"}
    )

    report = fuse_telemetry([first, second])

    assert report.fused_record_count == 0
    assert report.unresolved_record_count == 2
