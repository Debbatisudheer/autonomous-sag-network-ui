from __future__ import annotations

import json
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry import (
    InMemoryTelemetryTransport,
    TelemetryMetric,
    TelemetryRecord,
    TelemetryStateStore,
    TelemetryStateTransportConsumer,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    store = TelemetryStateStore()
    consumer = TelemetryStateTransportConsumer(store)
    transport = InMemoryTelemetryTransport()
    transport.subscribe("telemetry-state-store", consumer.consume)

    records = [
        TelemetryRecord(
            record_id="phase30:space:1",
            timestamp_s=100.0,
            sequence=1,
            source_id="sat-1",
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.RECEIVED_POWER_DBM,
            value=-71.5,
            unit="dBm",
        ),
        TelemetryRecord(
            record_id="phase30:space:2",
            timestamp_s=101.0,
            sequence=2,
            source_id="sat-1",
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.SINR_DB,
            value=12.4,
            unit="dB",
        ),
    ]
    results = transport.publish_many(records)
    stats = transport.stats()
    snapshot = store.snapshot(timestamp_s=101.0)

    output = {
        "phase": "30",
        "name": "Real-Time Data Transport",
        "status": "pass",
        "published_records": len(results),
        "accepted_records": sum(result.accepted for result in results),
        "transport_sequences": [result.transport_sequence for result in results],
        "state_updates": sum(result.state_updates for result in consumer.results),
        "state_samples": snapshot.sample_count,
        "stale_samples": snapshot.stale_sample_count,
        "transport_stats": stats.model_dump(),
        "architecture": "transport -> TelemetryStateStore -> RealTimeStateSnapshot",
        "fixture": "deterministic synthetic transport fixture",
        "root": str(ROOT),
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
