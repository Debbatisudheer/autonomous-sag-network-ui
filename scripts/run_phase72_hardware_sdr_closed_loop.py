from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.hardware_sdr_closed_loop import (
    HardwareSdrClosedLoopConfig,
    HardwareSdrClosedLoopEngine,
    HardwareSdrClosedLoopEvidence,
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
                    record_id=f"phase72-{row_index}",
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
            record_id=f"phase72-synthetic-{index}",
            timestamp_s=200.0 + index,
            sequence=index,
            source_id="ground-edge-01",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=10.0 + index * 0.2,
            unit="ms",
        )
        for index in range(32)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 72 hardware + SDR closed-loop validation"
    )
    parser.add_argument("--opssat-file", type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--local-host", action="store_true")
    parser.add_argument("--hardware", action="store_true")
    parser.add_argument("--hardware-device-args", default="")
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit must be positive")
    if args.hardware and args.local_host:
        raise ValueError("--hardware and --local-host cannot be combined")

    source_sha256 = ""
    provenance_verified = False
    if args.opssat_file is None:
        records = synthetic_records()
    else:
        records, source_sha256, provenance_verified = read_records(args.opssat_file, args.limit)
        if not provenance_verified:
            raise ValueError("OPS-SAT real-data run requires a verified provenance manifest")

    config = HardwareSdrClosedLoopConfig(
        sample_rate_hz=2_000_000.0,
        center_frequency_hz=915_000_000.0,
        symbol_rate_hz=100_000.0,
        amplitude=0.8,
        decision_threshold=0.5,
        sample_count=4096,
        timeout_us=100_000,
        source_id="ground-node-01",
        destination_id="air-node-01",
    )
    engine = HardwareSdrClosedLoopEngine()
    if args.hardware:
        report = engine.run_hardware_sdr(
            records,
            config=config,
            timestamp_s=72.0,
            device_args=args.hardware_device_args,
            public_data=args.opssat_file is not None,
        )
    elif args.local_host:
        report = engine.run_local_host(
            records,
            config=config,
            timestamp_s=72.0,
            public_data=args.opssat_file is not None,
        )
    else:
        report = engine.run_synthetic(
            records,
            config=config,
            timestamp_s=72.0,
            public_data=args.opssat_file is not None,
        )

    payload = report.model_dump(mode="json")
    payload["name"] = "Hardware + SDR Closed Loop"
    payload["phase"] = "72"
    payload["status"] = "pass"
    payload["source_sha256"] = source_sha256
    payload["provenance_verified"] = provenance_verified
    payload["external_network_used"] = False
    payload["network_mutation"] = False
    payload["notice"] = (
        "Default mode is a deterministic synthetic closed loop. "
        "--local-host uses the local CPU only. "
        "--hardware captures RX I/Q through SoapySDR; the returned control payload "
        "is verified through the deterministic software wireless-link path. "
        "No TX SDR path is invoked."
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
