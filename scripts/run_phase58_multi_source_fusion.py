from __future__ import annotations

import argparse
import json
from datetime import datetime, UTC
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.fusion import fuse_telemetry, FusionConfig
from sag_network.telemetry import (
    SatNOGSDecodedTelemetryAdapter,
    TelemetryMetric,
    TelemetryRecord,
    TelemetryTimeMapper,
)


def _mapper() -> TelemetryTimeMapper:
    return TelemetryTimeMapper(
        epoch_utc=datetime(2026, 1, 1, tzinfo=UTC),
        simulation_epoch_s=0.0,
    )


def _satnogs_fixture() -> list[dict[str, object]]:
    return [
        {
            "timestamp": "2026-01-01T00:00:10.5Z",
            "source_id": "sat-01",
            "metric": "sinr_db",
            "value": 22.0,
            "unit": "dB",
            "sequence": 1,
        }
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 58 multi-source telemetry fusion")
    parser.add_argument("--satnogs-json", type=Path, default=None)
    args = parser.parse_args()

    mapper = _mapper()
    satnogs_adapter = SatNOGSDecodedTelemetryAdapter(time_mapper=mapper)
    satnogs_payload: object = _satnogs_fixture()
    evidence_class = "SYNTHETIC FIXTURE"

    if args.satnogs_json is not None:
        satnogs_payload = json.loads(args.satnogs_json.read_text(encoding="utf-8"))
        evidence_class = "PUBLIC DATA"

    satnogs_records = satnogs_adapter.records_from_payload(
        satnogs_payload,
        source_uri=(
            "file://" + args.satnogs_json.resolve().as_posix()
            if args.satnogs_json is not None
            else None
        ),
    )

    opssat_record = TelemetryRecord(
        record_id="opssat:fixture:1",
        timestamp_s=10.0,
        sequence=0,
        source_id="sat-01",
        domain=NetworkDomain.SPACE,
        metric=TelemetryMetric.SINR_DB,
        value=20.0,
        unit="dB",
        metadata={
            "provenance_source": "ESA OPS-SAT / OPSSAT-AD segments.csv",
            "provenance_sha256": "phase56-public-dataset-fingerprint",
        },
    )
    report = fuse_telemetry(
        [opssat_record, *satnogs_records],
        config=FusionConfig(timestamp_tolerance_s=1.0),
    )

    print(
        json.dumps(
            {
                "name": "Multi-Source Telemetry Fusion",
                "phase": "58",
                "status": "pass",
                "evidence_class": evidence_class,
                "input_record_count": report.input_record_count,
                "provenance_source_count": report.provenance_source_count,
                "fused_record_count": report.fused_record_count,
                "unresolved_record_count": report.unresolved_record_count,
                "conflict_count": report.conflict_count,
                "source_names": report.source_names,
                "fused_values": [item.value for item in report.fused],
                "fusion_fingerprint": report.fingerprint,
                "network_mutation": False,
                "notice": (
                    "The default run uses an offline fusion fixture. "
                    "Pass --satnogs-json only when using a retrieved public SatNOGS payload."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
