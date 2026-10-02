from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.history import HistoricalDatasetConfig, HistoricalDatasetStore, HistoricalQuery
from sag_network.telemetry import TelemetryMetric, TelemetryRecord


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="sag-phase31-"))
    try:
        store = HistoricalDatasetStore(root, config=HistoricalDatasetConfig(partition_span_s=10))
        store.create("phase31-demo")
        records = [
            TelemetryRecord(
                record_id="phase31-r1",
                timestamp_s=1.0,
                sequence=1,
                source_id="sat-1",
                domain=NetworkDomain.SPACE,
                metric=TelemetryMetric.SINR_DB,
                value=8.0,
                unit="dB",
                metadata={"provenance_sha256": "synthetic-phase31"},
            ),
            TelemetryRecord(
                record_id="phase31-r2",
                timestamp_s=12.0,
                sequence=2,
                source_id="uav-1",
                domain=NetworkDomain.AIR,
                metric=TelemetryMetric.LATENCY_MS,
                value=14.0,
                unit="ms",
                metadata={"provenance_sha256": "synthetic-phase31"},
            ),
        ]
        accepted = store.append("phase31-demo", records)
        manifest = store.seal("phase31-demo")
        result = store.query("phase31-demo", HistoricalQuery(start_time_s=0, end_time_s=20))
        payload = {
            "name": "Historical Dataset Platform",
            "phase": "31",
            "status": "pass",
            "accepted_records": accepted,
            "queried_records": result.count,
            "partition_count": manifest.partition_count,
            "record_count": manifest.record_count,
            "dataset_status": manifest.status.value,
            "dataset_fingerprint": manifest.dataset_fingerprint,
            "storage": "partitioned deterministic JSONL + manifest",
            "fixture": "synthetic historical telemetry fixture",
            "query_order": [record.record_id for record in result.records],
        }
        print(json.dumps(payload, indent=2))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
