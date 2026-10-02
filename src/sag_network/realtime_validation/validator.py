from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from collections.abc import Iterable

from sag_network.realtime_validation.models import (
    TelemetryValidationReport,
    ValidationRejection,
)
from sag_network.telemetry.models import TelemetryQuality, TelemetryRecord


class TelemetryValidationError(ValueError):
    """Raised when a real-time validation configuration is invalid."""


class RealTimeTelemetryValidator:
    """Validate normalized telemetry before it enters the authoritative state store.

    This layer intentionally checks data-integrity and temporal invariants only. It
    does not invent domain-specific physical limits, because those limits depend on
    the instrument, mission, metric, and calibration context.
    """

    def __init__(
        self,
        *,
        reject_invalid_quality: bool = True,
        reject_future_records: bool = True,
        max_future_skew_s: float = 0.0,
        enforce_stream_monotonicity: bool = True,
    ) -> None:
        if max_future_skew_s < 0 or not math.isfinite(max_future_skew_s):
            raise TelemetryValidationError("max_future_skew_s must be finite and non-negative")
        self.reject_invalid_quality = reject_invalid_quality
        self.reject_future_records = reject_future_records
        self.max_future_skew_s = max_future_skew_s
        self.enforce_stream_monotonicity = enforce_stream_monotonicity

    def validate(
        self,
        records: Iterable[TelemetryRecord],
        *,
        reference_time_s: float,
    ) -> tuple[tuple[TelemetryRecord, ...], TelemetryValidationReport]:
        if reference_time_s < 0 or not math.isfinite(reference_time_s):
            raise TelemetryValidationError("reference_time_s must be finite and non-negative")

        accepted: list[TelemetryRecord] = []
        accepted_ids: list[str] = []
        rejected: list[ValidationRejection] = []
        rejected_ids: list[str] = []
        reasons: Counter[str] = Counter()
        seen_ids: set[str] = set()
        latest_by_key: dict[tuple[str, str], TelemetryRecord] = {}

        for record in records:
            reason = self._validate_record(
                record,
                reference_time_s=reference_time_s,
                seen_ids=seen_ids,
                latest_by_key=latest_by_key,
            )
            if reason is not None:
                rejected.append(ValidationRejection(record.record_id, reason))
                rejected_ids.append(record.record_id)
                reasons[reason] += 1
                continue

            seen_ids.add(record.record_id)
            key = (record.source_id, record.metric.value)
            latest_by_key[key] = record
            accepted.append(record)
            accepted_ids.append(record.record_id)

        payload = {
            "input_record_count": len(accepted) + len(rejected),
            "accepted_record_count": len(accepted),
            "rejected_record_count": len(rejected),
            "rejection_reasons": dict(sorted(reasons.items())),
            "accepted_record_ids": accepted_ids,
            "rejected_record_ids": rejected_ids,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        report = TelemetryValidationReport(
            input_record_count=len(accepted) + len(rejected),
            accepted_record_count=len(accepted),
            rejected_record_count=len(rejected),
            rejection_reasons=dict(sorted(reasons.items())),
            accepted_record_ids=tuple(accepted_ids),
            rejected_record_ids=tuple(rejected_ids),
            validation_fingerprint=fingerprint,
        )
        return tuple(accepted), report

    def _validate_record(
        self,
        record: TelemetryRecord,
        *,
        reference_time_s: float,
        seen_ids: set[str],
        latest_by_key: dict[tuple[str, str], TelemetryRecord],
    ) -> str | None:
        if record.record_id in seen_ids:
            return "record_id is duplicated in this validation stream"
        if not math.isfinite(record.timestamp_s):
            return "record timestamp is not finite"
        if not math.isfinite(record.value):
            return "telemetry value is not finite"
        if self.reject_invalid_quality and record.quality is TelemetryQuality.INVALID:
            return "telemetry quality is invalid"
        if self.reject_future_records and (
            record.timestamp_s > reference_time_s + self.max_future_skew_s
        ):
            return "record timestamp is beyond validation future skew"

        if self.enforce_stream_monotonicity:
            previous = latest_by_key.get((record.source_id, record.metric.value))
            if previous is not None and record.sequence <= previous.sequence:
                return "sequence is not strictly increasing within validation stream"
            if previous is not None and record.timestamp_s < previous.timestamp_s:
                return "timestamp is older than previous validation record"
        return None
