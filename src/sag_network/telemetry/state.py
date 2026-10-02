from __future__ import annotations

from collections import deque

from sag_network.telemetry.models import (
    RealTimeStateSnapshot,
    TelemetryBatch,
    TelemetryIngestionConfig,
    TelemetryIngestResult,
    TelemetryRecord,
    TelemetryRejection,
    TelemetryStateSample,
)


class TelemetryStateStore:
    """Deterministic latest-value store with sequence protection and stale-state evaluation."""

    def __init__(self, config: TelemetryIngestionConfig | None = None) -> None:
        self.config = config or TelemetryIngestionConfig()
        self._latest: dict[tuple[str, str], TelemetryRecord] = {}
        self._seen_record_ids: set[str] = set()
        self._history: deque[TelemetryRecord] = deque(maxlen=self.config.history_limit)

    @property
    def history(self) -> tuple[TelemetryRecord, ...]:
        return tuple(self._history)

    @property
    def latest_records(self) -> tuple[TelemetryRecord, ...]:
        return tuple(
            sorted(
                self._latest.values(),
                key=lambda record: (record.source_id, record.metric.value),
            )
        )

    def ingest(self, record: TelemetryRecord, *, reference_time_s: float) -> TelemetryIngestResult:
        """Ingest one record against the supplied simulation-time reference."""
        rejection = self._validate_record(record, reference_time_s=reference_time_s)
        if rejection is not None:
            return TelemetryIngestResult(
                accepted_record_ids=[],
                rejected_records=[rejection],
                state_updates=0,
            )

        key = (record.source_id, record.metric.value)
        previous = self._latest.get(key)
        if previous is not None:
            if self.config.enforce_monotonic_sequence:
                if record.sequence < previous.sequence:
                    return TelemetryIngestResult(
                        accepted_record_ids=[],
                        rejected_records=[
                            TelemetryRejection(
                                record_id=record.record_id,
                                reason="sequence is older than latest accepted sequence",
                            )
                        ],
                        state_updates=0,
                    )
                if record.sequence == previous.sequence:
                    return TelemetryIngestResult(
                        accepted_record_ids=[],
                        rejected_records=[
                            TelemetryRejection(
                                record_id=record.record_id,
                                reason="sequence duplicates latest accepted sequence",
                            )
                        ],
                        state_updates=0,
                    )
            if self.config.enforce_monotonic_timestamp and record.timestamp_s < previous.timestamp_s:
                return TelemetryIngestResult(
                    accepted_record_ids=[],
                    rejected_records=[
                        TelemetryRejection(
                            record_id=record.record_id,
                            reason="timestamp is older than latest accepted timestamp",
                        )
                    ],
                    state_updates=0,
                )

        self._latest[key] = record
        self._seen_record_ids.add(record.record_id)
        self._history.append(record)
        return TelemetryIngestResult(
            accepted_record_ids=[record.record_id],
            rejected_records=[],
            state_updates=1,
        )

    def ingest_batch(
        self,
        batch: TelemetryBatch,
        *,
        reference_time_s: float | None = None,
    ) -> TelemetryIngestResult:
        """Ingest a telemetry batch independently while preserving input order."""
        accepted: list[str] = []
        rejected: list[TelemetryRejection] = []
        updates = 0
        for record in batch.records:
            result = self.ingest(
                record,
                reference_time_s=batch.timestamp_s if reference_time_s is None else reference_time_s,
            )
            accepted.extend(result.accepted_record_ids)
            rejected.extend(result.rejected_records)
            updates += result.state_updates
        return TelemetryIngestResult(
            accepted_record_ids=accepted,
            rejected_records=rejected,
            state_updates=updates,
        )

    def snapshot(self, *, timestamp_s: float) -> RealTimeStateSnapshot:
        """Materialize the latest state and calculate sample age/staleness at a simulation instant."""
        samples = [
            TelemetryStateSample(
                source_id=record.source_id,
                domain=record.domain,
                metric=record.metric,
                value=record.value,
                unit=record.unit,
                timestamp_s=record.timestamp_s,
                sequence=record.sequence,
                age_s=max(0.0, timestamp_s - record.timestamp_s),
                quality=record.quality,
                stale=(timestamp_s - record.timestamp_s) > self.config.stale_after_s,
                metadata=record.metadata.copy(),
            )
            for record in self.latest_records
        ]
        return RealTimeStateSnapshot(timestamp_s=timestamp_s, samples=samples)

    def latest_for(self, *, source_id: str, metric: str) -> TelemetryRecord | None:
        """Return the latest accepted record for one source/metric pair."""
        return self._latest.get((source_id, metric))

    def _validate_record(
        self,
        record: TelemetryRecord,
        *,
        reference_time_s: float,
    ) -> TelemetryRejection | None:
        if record.record_id in self._seen_record_ids:
            return TelemetryRejection(
                record_id=record.record_id,
                reason="record_id has already been accepted",
            )
        if self.config.reject_future_records and (
            record.timestamp_s > reference_time_s + self.config.max_future_skew_s
        ):
            return TelemetryRejection(
                record_id=record.record_id,
                reason="record timestamp is beyond allowed future skew",
            )
        return None
