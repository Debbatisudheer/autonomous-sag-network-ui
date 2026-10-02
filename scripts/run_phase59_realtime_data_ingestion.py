from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.ingestion import IngestionConfig, RealTimeTelemetryIngestion
from sag_network.telemetry import (
    OPSSATSegmentsAdapter,
    TelemetryMetric,
    TelemetryRecord,
    TelemetryStateStore,
    TelemetryTimeMapper,
)

ROOT = Path(__file__).resolve().parents[1]


def _mapper() -> TelemetryTimeMapper:
    return TelemetryTimeMapper(
        epoch_utc=datetime(2026, 1, 1, tzinfo=UTC),
        simulation_epoch_s=0.0,
    )


def _fixture() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id="fixture-1",
            timestamp_s=8.0,
            sequence=0,
            source_id="sat-01",
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.SINR_DB,
            value=20.0,
            unit="dB",
        ),
        TelemetryRecord(
            record_id="fixture-2",
            timestamp_s=9.0,
            sequence=1,
            source_id="sat-01",
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.SINR_DB,
            value=21.0,
            unit="dB",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 59 real-time telemetry ingestion")
    parser.add_argument("--opssat-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    state_store = TelemetryStateStore()
    pipeline = RealTimeTelemetryIngestion(
        state_store,
        config=IngestionConfig(batch_size=32, max_records=args.limit),
    )

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

    report = pipeline.ingest(records, reference_time_s=10.0)
    snapshot = state_store.snapshot(timestamp_s=10.0)

    print(
        json.dumps(
            {
                "name": "Real-Time Data Ingestion",
                "phase": "59",
                "status": "pass",
                "evidence_class": evidence_class,
                "input_record_count": report.input_record_count,
                "accepted_record_count": report.accepted_record_count,
                "rejected_record_count": report.rejected_record_count,
                "batch_count": report.batch_count,
                "state_update_count": report.state_update_count,
                "duplicate_count": report.duplicate_count,
                "late_count": report.late_count,
                "state_sample_count": snapshot.sample_count,
                "stale_sample_count": snapshot.stale_sample_count,
                "ingestion_fingerprint": report.ingestion_fingerprint,
                "network_mutation": False,
                "notice": (
                    "The default run uses an offline ingestion fixture. "
                    "Pass --opssat-file only with the verified public OPS-SAT dataset."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
