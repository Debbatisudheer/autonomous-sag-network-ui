from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.network_telemetry_loop import (
    NetworkLoopEvidence,
    NetworkTelemetryLoopEngine,
    SyntheticTelemetryLoopTransport,
)
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


def read_records(path: Path, limit: int | None, metric: TelemetryMetric) -> tuple[list[TelemetryRecord], str, bool]:
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
            if limit is not None and len(records) >= limit:
                break
            value = float(row["value"])
            timestamp = parse_timestamp(row["timestamp"])
            channel = row.get("channel", "opssat") or "opssat"
            records.append(
                TelemetryRecord(
                    record_id=f"phase70-{row_index}",
                    timestamp_s=timestamp,
                    sequence=row_index - 1,
                    source_id=channel,
                    domain=NetworkDomain.SPACE,
                    metric=metric,
                    value=value,
                    unit="dataset-value",
                )
            )
    return records, source_sha256, provenance_verified


def run(records: list[TelemetryRecord], *, evidence: NetworkLoopEvidence, source_sha256: str, provenance_verified: bool, udp: bool) -> dict[str, object]:
    engine = NetworkTelemetryLoopEngine()
    reference_time_s = max((record.timestamp_s for record in records), default=0.0) + 1.0
    if udp:
        report = engine.run_udp_loopback(
            records,
            reference_time_s=reference_time_s,
            evidence_class=NetworkLoopEvidence.LOCAL_NETWORK_TEST,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )
    else:
        report = engine.run(
            records,
            reference_time_s=reference_time_s,
            transport=SyntheticTelemetryLoopTransport(),
            evidence_class=evidence,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )
    return report.model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 70 real network telemetry loop validation")
    parser.add_argument("--opssat-file", type=Path)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--metric", default="latency_ms", choices=[metric.value for metric in TelemetryMetric])
    parser.add_argument("--udp-loopback", action="store_true")
    args = parser.parse_args()
    if args.opssat_file is None:
        records = [
            TelemetryRecord(
                record_id=f"synthetic-{index}",
                timestamp_s=100.0 + index,
                sequence=index,
                source_id="ground-node-01",
                domain=NetworkDomain.GROUND,
                metric=TelemetryMetric.LATENCY_MS,
                value=10.0 + index * 0.25,
                unit="ms",
            )
            for index in range(16)
        ]
        payload = run(
            records,
            evidence=NetworkLoopEvidence.SYNTHETIC_FIXTURE,
            source_sha256="",
            provenance_verified=False,
            udp=args.udp_loopback,
        )
    else:
        records, source_sha256, provenance_verified = read_records(args.opssat_file, args.limit, TelemetryMetric(args.metric))
        if not provenance_verified:
            raise ValueError("OPS-SAT real-data run requires a verified provenance manifest")
        payload = run(
            records,
            evidence=NetworkLoopEvidence.PUBLIC_DATA,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            udp=args.udp_loopback,
        )
    payload["name"] = "Real Network Telemetry Loop"
    payload["phase"] = "70"
    payload["status"] = "pass"
    payload["notice"] = "Default mode is a deterministic software loopback. --udp-loopback uses only 127.0.0.1. It is not external network evidence."
    print(json.dumps(payload, sort_keys=False, indent=2))


if __name__ == "__main__":
    main()
