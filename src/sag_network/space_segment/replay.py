from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def parse_timestamp(value: str) -> float:
    """Parse numeric or timezone-aware ISO-8601 telemetry timestamps."""
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        parsed = datetime.fromisoformat(stripped)
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include timezone information")
        return parsed.timestamp()


def read_public_records(
    path: Path,
    limit: int,
) -> tuple[list[TelemetryRecord], str, bool]:
    """Read verified public telemetry and normalize timestamps to elapsed replay time."""
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    provenance_verified = False
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != source_sha256:
            raise ValueError("dataset manifest SHA-256 mismatch")
        provenance_verified = manifest.get("verified") is True
    if not provenance_verified:
        raise ValueError("public-data run requires a verified provenance manifest")

    raw_rows: list[tuple[float, str, float, int]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row_index, row in enumerate(reader, start=1):
            if len(raw_rows) >= limit:
                break
            raw_rows.append(
                (
                    parse_timestamp(row["timestamp"]),
                    row.get("channel", "opssat") or "opssat",
                    float(row["value"]),
                    row_index,
                )
            )

    if not raw_rows:
        raise ValueError("public dataset contains no records in requested limit")

    origin = raw_rows[0][0]
    records = [
        TelemetryRecord(
            record_id=f"phase75-{row_index}",
            timestamp_s=timestamp_s - origin,
            sequence=index,
            source_id=source_id,
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.LATENCY_MS,
            value=value,
            unit="dataset-value",
            metadata={"source_timestamp_s": str(timestamp_s)},
        )
        for index, (timestamp_s, source_id, value, row_index) in enumerate(raw_rows)
    ]
    return records, source_sha256, provenance_verified
