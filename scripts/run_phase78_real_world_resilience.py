from __future__ import annotations

import argparse
import json
from pathlib import Path

from sag_network.cross_domain_sag import CrossDomainSAGEvidence
from sag_network.resilience_campaign import (
    ResilienceCampaignConfig,
    ResilienceCampaignEngine,
    default_resilience_scenarios,
)
from sag_network.space_segment.replay import read_public_records
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord
from sag_network.domain.unified import NetworkDomain


def synthetic_records(count: int = 16) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase78-synthetic-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="phase78-synthetic",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=5.0 + index * 0.1,
            unit="ms",
        )
        for index in range(count)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 78 Real-World Resilience Campaign")
    parser.add_argument("--opssat-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--udp-loopback", action="store_true")
    parser.add_argument("--real-ephemeris", action="store_true")
    parser.add_argument(
        "--timestamps",
        type=float,
        nargs="*",
        default=[0.0, 300.0, 600.0, 900.0, 1200.0, 1500.0, 1800.0, 2100.0, 2400.0, 2700.0, 3000.0],
    )
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

    report = ResilienceCampaignEngine().run(
        records,
        default_resilience_scenarios(),
        config=ResilienceCampaignConfig(
            timestamps_s=args.timestamps,
            user_demand_bps={
                "sag-user-01": 10e6,
                "sag-user-02": 10e6,
                "sag-user-03": 10e6,
            },
            use_real_ephemeris=use_real_ephemeris,
            use_udp_loopback=args.udp_loopback,
            timeout_s=1.0,
        ),
        evidence_class=evidence,
        source_sha256=source_sha256,
        provenance_verified=provenance_verified,
    )
    output = report.model_dump(mode="json")
    output["notice"] = (
        "Phase 78 runs a controlled resilience campaign over the validated Phase 77 closed-loop "
        "autonomy boundary. Faults are deterministic software-side injections into candidate state, "
        "capacity, or telemetry-health gates; they do not mutate real network infrastructure. "
        "Ground and Air resources remain project fixtures, while the optional SGP4 path uses the "
        "bundled point-in-time ISS/ZARYA public TLE. OPS-SAT telemetry is public replay input and "
        "is not a measured end-to-end SAG link. Physical RF transmission and hardware actuation are "
        "not invoked by this phase."
    )
    print(json.dumps(output, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
