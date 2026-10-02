from __future__ import annotations

import argparse
import json
from datetime import datetime, UTC
from io import StringIO
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry import (
    CSVTelemetryAdapter,
    iter_space_packets,
    OPSSATSegmentsAdapter,
    SatNOGSDecodedTelemetryAdapter,
    TelemetryMetric,
    TelemetrySchema,
    TelemetryStateStore,
    TelemetryTimeMapper,
)

ROOT = Path(__file__).resolve().parents[1]


def _mapper() -> TelemetryTimeMapper:
    return TelemetryTimeMapper(
        epoch_utc=datetime(2026, 1, 1, tzinfo=UTC),
        simulation_epoch_s=0.0,
    )


def _synthetic_csv() -> str:
    return (
        "timestamp,source_id,value,metric,domain,unit,sequence\n"
        "2026-01-01T00:00:01Z,sat-demo,8.0,sinr_db,space,dB,0\n"
        "2026-01-01T00:00:02Z,sat-demo,-80.0,received_power_dbm,space,dBm,1\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 29 real telemetry adapter validation")
    parser.add_argument("--opssat-file", type=Path, default=None)
    args = parser.parse_args()

    time_mapper = _mapper()
    csv_adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(
            timestamp="timestamp",
            value="value",
            source_id="source_id",
            metric="metric",
            domain="domain",
            unit="unit",
            sequence="sequence",
        ),
        time_mapper=time_mapper,
        source_name="Phase 29 synthetic schema fixture",
    )
    records = list(csv_adapter.iter_records(StringIO(_synthetic_csv())))

    store = TelemetryStateStore()
    accepted = 0
    for record in records:
        accepted += store.ingest(record, reference_time_s=record.timestamp_s).accepted_count

    opssat_records = 0
    if args.opssat_file is not None:
        opssat_records = len(
            OPSSATSegmentsAdapter(time_mapper=time_mapper).read_path(args.opssat_file)
        )

    satnogs_records = len(
        SatNOGSDecodedTelemetryAdapter(time_mapper=time_mapper).records_from_payload(
            [
                {
                    "timestamp": "2026-01-01T00:00:03Z",
                    "source_id": "satnogs-demo",
                    "metric": "doppler_shift_hz",
                    "value": -1234.0,
                    "unit": "Hz",
                    "sequence": 0,
                }
            ]
        )
    )

    ccsds_example = bytes.fromhex("000100010002414243")
    packet_count = len(list(iter_space_packets(ccsds_example)))

    snapshot = store.snapshot(timestamp_s=2.0)
    print(
        json.dumps(
            {
                "status": "pass",
                "phase": "29",
                "name": "Real Telemetry Adapters",
                "synthetic_fixture": True,
                "synthetic_fixture_notice": (
                    "Built-in CSV and SatNOGS samples are schema fixtures, "
                    "not real measurements."
                ),
                "csv_records": len(records),
                "state_updates": accepted,
                "state_samples": snapshot.sample_count,
                "stale_samples": snapshot.stale_sample_count,
                "opssat_records": opssat_records,
                "satnogs_records": satnogs_records,
                "ccsds_packets": packet_count,
                "adapter_metrics": [
                    TelemetryMetric.SINR_DB.value,
                    TelemetryMetric.RECEIVED_POWER_DBM.value,
                ],
                "domain": NetworkDomain.SPACE.value,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
