from __future__ import annotations

from sag_network.domain.unified import NetworkDomain
from sag_network.ingestion import IngestionConfig, RealTimeTelemetryIngestion
from sag_network.telemetry import TelemetryMetric, TelemetryRecord, TelemetryStateStore


def _record(record_id: str, sequence: int, timestamp_s: float, value: float) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=sequence,
        source_id="sat-01",
        domain=NetworkDomain.SPACE,
        metric=TelemetryMetric.SINR_DB,
        value=value,
        unit="dB",
    )


def test_ingestion_batches_and_updates_existing_state_store() -> None:
    store = TelemetryStateStore()
    pipeline = RealTimeTelemetryIngestion(store, config=IngestionConfig(batch_size=2))
    report = pipeline.ingest(
        [_record("r1", 0, 8.0, 20.0), _record("r2", 1, 9.0, 21.0)],
        reference_time_s=10.0,
    )

    assert report.input_record_count == 2
    assert report.accepted_record_count == 2
    assert report.batch_count == 1
    assert report.state_update_count == 2
    assert report.rejected_record_count == 0
    assert store.latest_for(source_id="sat-01", metric="sinr_db").value == 21.0


def test_duplicate_ids_are_rejected_at_stream_boundary() -> None:
    store = TelemetryStateStore()
    pipeline = RealTimeTelemetryIngestion(store)
    report = pipeline.ingest(
        [_record("r1", 0, 8.0, 20.0), _record("r1", 1, 9.0, 21.0)],
        reference_time_s=10.0,
    )

    assert report.accepted_record_count == 1
    assert report.rejected_record_count == 1
    assert report.duplicate_count == 1
    assert report.rejection_reasons == {
        "record_id is duplicated in this ingestion stream": 1
    }


def test_late_records_are_counted_without_being_silently_dropped() -> None:
    store = TelemetryStateStore()
    pipeline = RealTimeTelemetryIngestion(
        store,
        config=IngestionConfig(allowed_lateness_s=1.0),
    )
    report = pipeline.ingest(
        [_record("r1", 0, 7.0, 20.0)],
        reference_time_s=10.0,
    )

    assert report.late_count == 1
    assert report.accepted_record_count == 1


def test_max_records_limits_stream_consumption_deterministically() -> None:
    store = TelemetryStateStore()
    pipeline = RealTimeTelemetryIngestion(
        store,
        config=IngestionConfig(max_records=2, batch_size=1),
    )
    report = pipeline.ingest(
        [
            _record("r1", 0, 8.0, 20.0),
            _record("r2", 1, 9.0, 21.0),
            _record("r3", 2, 10.0, 22.0),
        ],
        reference_time_s=10.0,
    )

    assert report.input_record_count == 2
    assert report.accepted_record_ids == ("r1", "r2")
    assert report.batch_count == 2


def test_repeated_ingestion_is_fingerprinted_deterministically() -> None:
    records = [_record("r1", 0, 8.0, 20.0), _record("r2", 1, 9.0, 21.0)]
    first = RealTimeTelemetryIngestion(TelemetryStateStore()).ingest(
        records,
        reference_time_s=10.0,
    )
    second = RealTimeTelemetryIngestion(TelemetryStateStore()).ingest(
        records,
        reference_time_s=10.0,
    )

    assert first.ingestion_fingerprint == second.ingestion_fingerprint
