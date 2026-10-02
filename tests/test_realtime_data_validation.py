from __future__ import annotations

import math

from sag_network.domain.unified import NetworkDomain
from sag_network.realtime_validation import RealTimeTelemetryValidator
from sag_network.telemetry import TelemetryMetric, TelemetryQuality, TelemetryRecord


def _record(record_id: str, sequence: int, timestamp_s: float, value: float = 20.0, quality: TelemetryQuality = TelemetryQuality.GOOD) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=sequence,
        source_id="sat-01",
        domain=NetworkDomain.SPACE,
        metric=TelemetryMetric.SINR_DB,
        value=value,
        unit="dB",
        quality=quality,
    )


def test_validator_accepts_finite_good_records() -> None:
    accepted, report = RealTimeTelemetryValidator().validate(
        [_record("r1", 0, 8.0), _record("r2", 1, 9.0)], reference_time_s=10.0
    )
    assert len(accepted) == 2
    assert report.rejected_record_count == 0


def test_validator_rejects_non_finite_value() -> None:
    accepted, report = RealTimeTelemetryValidator().validate(
        [_record("r1", 0, 8.0, math.nan)], reference_time_s=10.0
    )
    assert not accepted
    assert report.rejection_reasons == {"telemetry value is not finite": 1}


def test_validator_rejects_invalid_quality() -> None:
    accepted, report = RealTimeTelemetryValidator().validate(
        [_record("r1", 0, 8.0, quality=TelemetryQuality.INVALID)], reference_time_s=10.0
    )
    assert not accepted
    assert report.rejection_reasons == {"telemetry quality is invalid": 1}


def test_validator_rejects_future_record() -> None:
    accepted, report = RealTimeTelemetryValidator().validate(
        [_record("r1", 0, 11.0)], reference_time_s=10.0
    )
    assert not accepted
    assert report.rejection_reasons == {"record timestamp is beyond validation future skew": 1}


def test_validator_rejects_non_monotonic_sequence() -> None:
    accepted, report = RealTimeTelemetryValidator().validate(
        [_record("r1", 1, 8.0), _record("r2", 1, 9.0)], reference_time_s=10.0
    )
    assert len(accepted) == 1
    assert report.rejection_reasons == {
        "sequence is not strictly increasing within validation stream": 1
    }


def test_validation_fingerprint_is_deterministic() -> None:
    records = [_record("r1", 0, 8.0), _record("r2", 1, 9.0)]
    first = RealTimeTelemetryValidator().validate(records, reference_time_s=10.0)[1]
    second = RealTimeTelemetryValidator().validate(records, reference_time_s=10.0)[1]
    assert first.validation_fingerprint == second.validation_fingerprint
