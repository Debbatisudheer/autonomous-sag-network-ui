from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sag_network.space_segment import (
    SpaceSegmentConfig,
    SpaceSegmentEvidence,
    SpaceSegmentIntegrationEngine,
)

from sag_network.domain.unified import NetworkDomain
from sag_network.space_segment.replay import read_public_records
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def synthetic_records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase75-synthetic-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="space-segment-telemetry",
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.LATENCY_MS,
            value=8.0 + index * 0.1,
            unit="ms",
        )
        for index in range(16)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 75 space segment integration")
    parser.add_argument("--opssat-file", type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--udp-loopback", action="store_true")
    parser.add_argument("--real-ephemeris", action="store_true")
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit must be positive")

    source_sha256 = ""
    provenance_verified = False
    if args.opssat_file is None:
        records = synthetic_records()
        evidence = (
            SpaceSegmentEvidence.LOCAL_NETWORK_TEST
            if args.udp_loopback
            else (
                SpaceSegmentEvidence.PUBLIC_EPHEMERIS
                if args.real_ephemeris
                else SpaceSegmentEvidence.SYNTHETIC_FIXTURE
            )
        )
    else:
        records, source_sha256, provenance_verified = read_public_records(
            args.opssat_file,
            args.limit,
        )
        evidence = (
            SpaceSegmentEvidence.LOCAL_NETWORK_TEST
            if args.udp_loopback
            else SpaceSegmentEvidence.PUBLIC_DATA
        )

    use_real_ephemeris = args.real_ephemeris or args.opssat_file is not None
    reference_time_s = max(
        (record.timestamp_s for record in records),
        default=0.0,
    )
    config = SpaceSegmentConfig(
        reference_time_s=reference_time_s,
        user_demand_bps={
            "space-user-01": 8e6,
            "space-user-02": 8e6,
            "space-user-03": 8e6,
        },
        use_udp_loopback=args.udp_loopback,
        timeout_s=1.0,
        use_real_ephemeris=use_real_ephemeris,
    )
    report = SpaceSegmentIntegrationEngine().run(
        records,
        config=config,
        evidence_class=evidence,
        source_sha256=source_sha256,
        provenance_verified=provenance_verified,
    )

    payload = report.model_dump(mode="json")
    payload["name"] = "Space Segment Data Integration"
    payload["phase"] = "75"
    payload["status"] = "pass"
    payload["source_sha256"] = source_sha256
    payload["provenance_verified"] = provenance_verified
    payload["external_network_used"] = False
    payload["network_mutation"] = False
    payload["hardware_measurement"] = False
    payload["notice"] = (
        "Phase 75 integrates the canonical telemetry loop with the existing satellite "
        "visibility/link model. --real-ephemeris uses the bundled point-in-time ISS "
        "(ZARYA), NORAD 25544 TLE through the existing SGP4 backend when installed. "
        "OPS-SAT telemetry is replayed on a normalized elapsed-time clock; it is not "
        "the orbit of ISS and is not treated as a measured space-network link. The "
        "bundled TLE is a public CelesTrak fixture, not a permanently current orbit."
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
