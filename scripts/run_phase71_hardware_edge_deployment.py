from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.hardware_edge import (
    EdgeWorkloadSpec,
    HardwareEdgeDeploymentEngine,
    HardwareEdgeEvidence,
    local_host_profile,
    synthetic_device_profile,
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
                    record_id=f"phase71-{row_index}",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 71 hardware edge deployment validation")
    parser.add_argument("--opssat-file", type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--local-host", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be positive")

    source_sha256 = ""
    provenance_verified = False
    if args.opssat_file is None:
        records = [
            TelemetryRecord(
                record_id=f"phase71-synthetic-{index}",
                timestamp_s=100.0 + index,
                sequence=index,
                source_id="ground-edge-01",
                domain=NetworkDomain.GROUND,
                metric=TelemetryMetric.LATENCY_MS,
                value=10.0 + index * 0.2,
                unit="ms",
            )
            for index in range(32)
        ]
        evidence = HardwareEdgeEvidence.LOCAL_HOST_MEASUREMENT if args.local_host else HardwareEdgeEvidence.SYNTHETIC_FIXTURE
    else:
        records, source_sha256, provenance_verified = read_records(args.opssat_file, args.limit)
        if not provenance_verified:
            raise ValueError("OPS-SAT real-data run requires a verified provenance manifest")
        evidence = HardwareEdgeEvidence.LOCAL_HOST_MEASUREMENT

    device = local_host_profile() if args.local_host else synthetic_device_profile()
    workload = EdgeWorkloadSpec(
        workload_id="telemetry-summary-v1",
        max_cpu_time_ms=50.0,
        max_python_heap_kb=512,
        max_wall_time_ms=100.0,
        maximum_input_records=max(128, args.limit),
    )
    report = HardwareEdgeDeploymentEngine().deploy(
        records,
        device=device,
        workload=workload,
        evidence_class=evidence,
    )
    payload = report.model_dump(mode="json")
    payload["name"] = "Hardware Edge Deployment"
    payload["phase"] = "71"
    payload["status"] = "pass" if report.workload.accepted else "degraded"
    payload["source_sha256"] = source_sha256
    payload["provenance_verified"] = provenance_verified
    payload["external_network_used"] = False
    payload["network_mutation"] = False
    payload["notice"] = (
        "Default mode uses a deterministic constrained edge fixture. --local-host observes and executes on the local host only; "
        "it is not evidence of deployment to a dedicated field edge device. OPS-SAT execution is historical public-data replay."
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
