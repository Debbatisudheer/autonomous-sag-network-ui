from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
import hashlib
import json

from pydantic import BaseModel, Field

from sag_network.realtime_validation import RealTimeTelemetryValidator
from sag_network.telemetry.models import (
    TelemetryBatch,
    TelemetryIngestResult,
    TelemetryRecord,
    TelemetryRejection,
)
from sag_network.telemetry.state import TelemetryStateStore


class IngestionError(ValueError):
    """Raised when a real-time ingestion configuration is invalid."""


class IngestionConfig(BaseModel):
    """Deterministic boundaries for incremental real-time telemetry ingestion."""

    batch_size: int = Field(default=32, ge=1)
    max_records: int | None = Field(default=None, ge=1)
    allowed_lateness_s: float = Field(default=0.0, ge=0)
    reject_duplicate_ids: bool = True


@dataclass(frozen=True)
class IngestionReport:
    """Immutable summary of one incremental ingestion run."""

    input_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    batch_count: int
    state_update_count: int
    duplicate_count: int
    late_count: int
    rejection_reasons: dict[str, int]
    accepted_record_ids: tuple[str, ...]
    rejected_record_ids: tuple[str, ...]
    ingestion_fingerprint: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RealTimeTelemetryIngestion:
    """Incrementally validate and commit normalized telemetry into the state store.

    The pipeline consumes an iterator, so callers can connect adapters, transports,
    or other streaming producers without constructing a second telemetry state model.
    The state store remains the authoritative latest-value read model.
    """

    def __init__(
        self,
        state_store: TelemetryStateStore,
        *,
        config: IngestionConfig | None = None,
        validator: RealTimeTelemetryValidator | None = None,
    ) -> None:
        self.state_store = state_store
        self.config = config or IngestionConfig()
        self.validator = validator

    def ingest(
        self,
        records: Iterable[TelemetryRecord],
        *,
        reference_time_s: float,
    ) -> IngestionReport:
        if reference_time_s < 0:
            raise IngestionError("reference_time_s must be non-negative")

        if self.validator is not None:
            validated_records, _validation_report = self.validator.validate(
                records, reference_time_s=reference_time_s
            )
            records = validated_records

        seen_ids: set[str] = set()
        accepted_ids: list[str] = []
        rejected_ids: list[str] = []
        rejection_reasons: Counter[str] = Counter()
        duplicate_count = 0
        late_count = 0
        input_count = 0
        batch_count = 0
        state_updates = 0
        batch: list[TelemetryRecord] = []

        for record in records:
            if (
                self.config.max_records is not None
                and input_count >= self.config.max_records
            ):
                break

            input_count += 1
            if record.record_id in seen_ids and self.config.reject_duplicate_ids:
                duplicate_count += 1
                rejection = TelemetryRejection(
                    record_id=record.record_id,
                    reason="record_id is duplicated in this ingestion stream",
                )
                rejected_ids.append(record.record_id)
                rejection_reasons[rejection.reason] += 1
                continue

            seen_ids.add(record.record_id)
            if record.timestamp_s < reference_time_s - self.config.allowed_lateness_s:
                late_count += 1

            batch.append(record)
            if len(batch) >= self.config.batch_size:
                result = self._commit_batch(batch, reference_time_s)
                batch_count += 1
                state_updates += result.state_updates
                accepted_ids.extend(result.accepted_record_ids)
                self._collect_rejections(result, rejected_ids, rejection_reasons)
                batch = []

        if batch:
            result = self._commit_batch(batch, reference_time_s)
            batch_count += 1
            state_updates += result.state_updates
            accepted_ids.extend(result.accepted_record_ids)
            self._collect_rejections(result, rejected_ids, rejection_reasons)

        payload = {
            "input_record_count": input_count,
            "accepted_record_count": len(accepted_ids),
            "rejected_record_count": len(rejected_ids),
            "batch_count": batch_count,
            "state_update_count": state_updates,
            "duplicate_count": duplicate_count,
            "late_count": late_count,
            "rejection_reasons": dict(sorted(rejection_reasons.items())),
            "accepted_record_ids": accepted_ids,
            "rejected_record_ids": rejected_ids,
        }
        return IngestionReport(
            input_record_count=input_count,
            accepted_record_count=len(accepted_ids),
            rejected_record_count=len(rejected_ids),
            batch_count=batch_count,
            state_update_count=state_updates,
            duplicate_count=duplicate_count,
            late_count=late_count,
            rejection_reasons=dict(sorted(rejection_reasons.items())),
            accepted_record_ids=tuple(accepted_ids),
            rejected_record_ids=tuple(rejected_ids),
            ingestion_fingerprint=_fingerprint(payload),
        )

    def _commit_batch(
        self,
        records: list[TelemetryRecord],
        reference_time_s: float,
    ) -> TelemetryIngestResult:
        return self.state_store.ingest_batch(
            self._batch(records, reference_time_s),
            reference_time_s=reference_time_s,
        )

    @staticmethod
    def _batch(
        records: list[TelemetryRecord],
        reference_time_s: float,
    ) -> TelemetryBatch:
        return TelemetryBatch(
            batch_id=_fingerprint([record.record_id for record in records])[:24],
            timestamp_s=reference_time_s,
            records=records,
            source="real-time-ingestion",
        )

    @staticmethod
    def _collect_rejections(
        result: TelemetryIngestResult,
        rejected_ids: list[str],
        rejection_reasons: Counter[str],
    ) -> None:
        for rejection in result.rejected_records:
            rejected_ids.append(rejection.record_id)
            rejection_reasons[rejection.reason] += 1
