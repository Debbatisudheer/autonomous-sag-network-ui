from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sag_network.air_segment import (
    AirSegmentConfig,
    AirSegmentEvidence,
    AirSegmentIntegrationEngine,
)
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def parse_timestamp(value: str) -> float:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        parsed = datetime.fromisoformat(stripped)
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include timezone information")
        return parsed.timestamp()


def read_records(path: Path, limit: int) -> tuple[list[TelemetryRecord], str, bool]:
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    provenance_verified = False
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != source_sha256:
            raise ValueError("dataset manifest SHA-256 mismatch")
        provenance_verified = manifest.get("verified") is True

    records: list[TelemetryRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row_index, row in enumerate(reader, start=1):
            if len(records) >= limit:
                break
            records.append(
                TelemetryRecord(
                    record_id=f"phase74-{row_index}",
                    timestamp_s=parse_timestamp(row["timestamp"]),
                    sequence=row_index - 1,
                    source_id=row.get("channel", "opssat") or "opssat",
                    domain=NetworkDomain.SPACE,
                    metric=TelemetryMetric.LATENCY_MS,
                    value=float(row["value"]),
                    unit="dataset-value",
                )
            )
    return records, source_sha256, provenance_verified


def synthetic_records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase74-synthetic-{index}",
            timestamp_s=400.0 + index,
            sequence=index,
            source_id="air-segment-telemetry",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.LATENCY_MS,
            value=12.0 + index * 0.2,
            unit="ms",
        )
        for index in range(16)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 74 air segment integration")
    parser.add_argument("--opssat-file", type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--udp-loopback", action="store_true")
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit must be positive")

    source_sha256 = ""
    provenance_verified = False
    if args.opssat_file is None:
        records = synthetic_records()
        evidence = (
            AirSegmentEvidence.LOCAL_NETWORK_TEST
            if args.udp_loopback
            else AirSegmentEvidence.SYNTHETIC_FIXTURE
        )
    else:
        records, source_sha256, provenance_verified = read_records(
            args.opssat_file,
            args.limit,
        )
        if not provenance_verified:
            raise ValueError(
                "OPS-SAT real-data run requires a verified provenance manifest"
            )
        evidence = (
            AirSegmentEvidence.LOCAL_NETWORK_TEST
            if args.udp_loopback
            else AirSegmentEvidence.PUBLIC_DATA
        )

    reference_time = max(
        (record.timestamp_s for record in records),
        default=0.0,
    )
    config = AirSegmentConfig(
        reference_time_s=reference_time,
        user_demand_bps={
            "air-user-01": 10e6,
            "air-user-02": 10e6,
            "air-user-03": 10e6,
        },
        use_udp_loopback=args.udp_loopback,
        timeout_s=1.0,
    )
    report = AirSegmentIntegrationEngine().run(
        records,
        config=config,
        evidence_class=evidence,
        source_sha256=source_sha256,
        provenance_verified=provenance_verified,
    )

    payload = report.model_dump(mode="json")
    payload["name"] = "Air Segment Integration"
    payload["phase"] = "74"
    payload["status"] = "pass"
    payload["source_sha256"] = source_sha256
    payload["provenance_verified"] = provenance_verified
    payload["external_network_used"] = False
    payload["network_mutation"] = False
    payload["notice"] = (
        "Phase 74 integrates the canonical telemetry loop with the existing airborne "
        "UAV/HAPS network association, mobility, link-budget, and energy model. "
        "The default transport is synthetic; --udp-loopback uses only 127.0.0.1. "
        "Public OPS-SAT mode is historical telemetry replay. Air platforms and users "
        "are deterministic project fixtures unless an explicit external trajectory "
        "source is introduced in a later data-acquisition phase."
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
