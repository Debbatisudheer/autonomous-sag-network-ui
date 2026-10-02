from __future__ import annotations

import argparse
import json
from pathlib import Path

from sag_network.autonomous_validation import (
    AutonomousSAGValidationEngine,
    AutonomousValidationConfig,
)
from sag_network.cross_domain_sag import CrossDomainSAGEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.space_segment.replay import read_public_records
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def synthetic_records(count: int = 16) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase79-synthetic-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="phase79-synthetic",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=5.0 + index * 0.1,
            unit="ms",
        )
        for index in range(count)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 79 Autonomous SAG Validation")
    parser.add_argument("--opssat-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--udp-loopback", action="store_true")
    parser.add_argument("--real-ephemeris", action="store_true")
    parser.add_argument("--timestamps", type=float, nargs="*", default=None)
    args = parser.parse_args()

    evidence = CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    source_sha256 = ""
    provenance_verified = False
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

    config_kwargs: dict[str, object] = {
        "use_real_ephemeris": use_real_ephemeris,
        "use_udp_loopback": args.udp_loopback,
        "timeout_s": 1.0,
    }
    if args.timestamps is not None:
        config_kwargs["timestamps_s"] = args.timestamps

    report = AutonomousSAGValidationEngine().run(
        records,
        config=AutonomousValidationConfig(**config_kwargs),
        evidence_class=evidence,
        source_sha256=source_sha256,
        provenance_verified=provenance_verified,
    )
    output = report.model_dump(mode="json")
    output["notice"] = (
        "Phase 79 validates the integrated Phase 76 cross-domain SAG network, Phase 77 closed-loop "
        "autonomy, and Phase 78 controlled resilience campaign. It is a repeatable software/research "
        "validation layer, not a claim of a deployed physical SAG network. Public OPS-SAT telemetry is "
        "replay input and the bundled ISS/ZARYA TLE is a point-in-time public ephemeris fixture. "
        "No external infrastructure is mutated and no RF/hardware actuation is invoked."
    )
    print(json.dumps(output, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
