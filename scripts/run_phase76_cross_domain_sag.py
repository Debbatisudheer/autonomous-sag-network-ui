from __future__ import annotations

import argparse
import json
from pathlib import Path

from sag_network.cross_domain_sag import (
    CrossDomainSAGConfig,
    CrossDomainSAGEvidence,
    CrossDomainSAGIntegrationEngine,
)
from sag_network.domain.unified import NetworkDomain
from sag_network.space_segment.replay import read_public_records
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def synthetic_records(count: int = 16) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase76-synthetic-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="phase76-synthetic",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=5.0 + index * 0.1,
            unit="ms",
        )
        for index in range(count)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 76 Cross-Domain SAG Network integration"
    )
    parser.add_argument("--opssat-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--udp-loopback", action="store_true")
    parser.add_argument("--real-ephemeris", action="store_true")
    args = parser.parse_args()

    source_sha256 = ""
    provenance_verified = False
    evidence = CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    use_real_ephemeris = args.real_ephemeris

    if args.opssat_file is not None:
        records, source_sha256, provenance_verified = read_public_records(
            args.opssat_file, args.limit
        )
        evidence = CrossDomainSAGEvidence.PUBLIC_DATA
        use_real_ephemeris = True
    else:
        records = synthetic_records()
        if args.real_ephemeris:
            evidence = CrossDomainSAGEvidence.PUBLIC_EPHEMERIS

    if args.udp_loopback:
        evidence = CrossDomainSAGEvidence.LOCAL_NETWORK_TEST

    report = CrossDomainSAGIntegrationEngine().run(
        records,
        config=CrossDomainSAGConfig(
            reference_time_s=15.0,
            user_demand_bps={
                "sag-user-01": 10e6,
                "sag-user-02": 10e6,
                "sag-user-03": 10e6,
            },
            use_udp_loopback=args.udp_loopback,
            timeout_s=1.0,
            use_real_ephemeris=use_real_ephemeris,
        ),
        evidence_class=evidence,
        source_sha256=source_sha256,
        provenance_verified=provenance_verified,
    )
    output = report.model_dump(mode="json")
    output["name"] = "Cross-Domain SAG Network"
    output["notice"] = (
        "Phase 76 composes one common user population across the validated Ground, Air, and "
        "Space link models. "
        "Ground and Air infrastructure remain deterministic project fixtures; --real-ephemeris "
        "uses the bundled "
        "point-in-time ISS/ZARYA NORAD 25544 public TLE through SGP4. OPS-SAT telemetry is "
        "public data replay input, "
        "not a measured end-to-end SAG link, and no external network or physical "
        "hardware is invoked."
    )
    print(json.dumps(output, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
