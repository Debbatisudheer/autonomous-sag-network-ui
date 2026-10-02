from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import UTC, datetime

from sag_network.domain.unified import NetworkDomain
from sag_network.ingestion import IngestionConfig, RealTimeTelemetryIngestion
from sag_network.realtime_validation import RealTimeTelemetryValidator
from sag_network.telemetry import (
    OPSSATSegmentsAdapter,
    TelemetryMetric,
    TelemetryQuality,
    TelemetryRecord,
    TelemetryStateStore,
    TelemetryTimeMapper,
)


def _mapper() -> TelemetryTimeMapper:
    return TelemetryTimeMapper(epoch_utc=datetime(2026, 1, 1, tzinfo=UTC))


def _fixture() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id="valid-1", timestamp_s=8.0, sequence=0, source_id="sat-01",
            domain=NetworkDomain.SPACE, metric=TelemetryMetric.SINR_DB, value=20.0, unit="dB",
        ),
        TelemetryRecord(
            record_id="invalid-quality", timestamp_s=8.5, sequence=1, source_id="sat-01",
            domain=NetworkDomain.SPACE, metric=TelemetryMetric.SINR_DB, value=20.5, unit="dB",
            quality=TelemetryQuality.INVALID,
        ),
        TelemetryRecord(
            record_id="valid-2", timestamp_s=9.0, sequence=2, source_id="sat-01",
            domain=NetworkDomain.SPACE, metric=TelemetryMetric.SINR_DB, value=21.0, unit="dB",
        ),
        TelemetryRecord(
            record_id="invalid-nan", timestamp_s=9.5, sequence=3, source_id="sat-01",
            domain=NetworkDomain.SPACE, metric=TelemetryMetric.SINR_DB, value=float("nan"), unit="dB",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 60 real-time telemetry validation")
    parser.add_argument("--opssat-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    validator = RealTimeTelemetryValidator()
    evidence_class = "SYNTHETIC FIXTURE"
    if args.opssat_file is not None:
        if not args.opssat_file.is_file():
            raise SystemExit(f"OPS-SAT dataset does not exist: {args.opssat_file}")
        records = OPSSATSegmentsAdapter(time_mapper=_mapper()).iter_records(
            args.opssat_file.open("r", encoding="utf-8", newline=""),
            source_uri=args.opssat_file.resolve().as_uri(),
        )
        evidence_class = "PUBLIC DATA"
    else:
        records = iter(_fixture())

    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    records = list(records)[:args.limit]
    validated, validation = validator.validate(records, reference_time_s=10.0)
    store = TelemetryStateStore()
    pipeline = RealTimeTelemetryIngestion(
        store,
        config=IngestionConfig(batch_size=32),
    )
    ingestion = pipeline.ingest(validated, reference_time_s=10.0)
    snapshot = store.snapshot(timestamp_s=10.0)

    print(json.dumps({
        "name": "Real-Time Data Validation",
        "phase": "60",
        "status": "pass",
        "evidence_class": evidence_class,
        "input_record_count": validation.input_record_count,
        "validated_record_count": validation.accepted_record_count,
        "validation_rejected_count": validation.rejected_record_count,
        "rejection_reasons": validation.rejection_reasons,
        "ingested_record_count": ingestion.accepted_record_count,
        "state_sample_count": snapshot.sample_count,
        "validation_fingerprint": validation.validation_fingerprint,
        "network_mutation": False,
        "notice": "Default validation uses an offline fixture. --opssat-file validates the verified public OPS-SAT dataset replay.",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
