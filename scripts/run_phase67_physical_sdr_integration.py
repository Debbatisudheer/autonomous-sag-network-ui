from __future__ import annotations

import argparse
import json

from sag_network.physical_sdr import (
    PhysicalSdrConfig,
    PhysicalSdrEvidence,
    PhysicalSdrIntegrationEngine,
    PhysicalSdrSource,
    SoapySdrRxBackend,
    SyntheticPhysicalSdrBackend,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 67 physical SDR RX integration")
    parser.add_argument("--hardware-device-args", default="")
    parser.add_argument("--hardware", action="store_true")
    args = parser.parse_args()

    config = PhysicalSdrConfig(
        channel=0,
        sample_rate_hz=2_000_000.0,
        center_frequency_hz=915_000_000.0,
        sample_count=4096,
        timeout_us=100_000,
    )

    if args.hardware:
        source = PhysicalSdrSource(SoapySdrRxBackend(args.hardware_device_args))
        evidence = PhysicalSdrEvidence.HARDWARE_MEASUREMENT
    else:
        source = PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6700))
        evidence = PhysicalSdrEvidence.SYNTHETIC_FIXTURE

    report = PhysicalSdrIntegrationEngine().process(
        source=source,
        config=config,
        timestamp_s=67.0,
        evidence_class=evidence,
    )
    print(json.dumps({
        "name": "Physical SDR Integration",
        "phase": "67",
        "status": "pass",
        "evidence_class": report.evidence_class.value,
        "sample_count": report.sample_count,
        "sample_rate_hz": report.sample_rate_hz,
        "center_frequency_hz": report.center_frequency_hz,
        "channel": report.channel,
        "mean_power": report.mean_power,
        "iq_imbalance_ratio": report.iq_imbalance_ratio,
        "sample_fingerprint": report.sample_fingerprint,
        "processing_fingerprint": report.processing_fingerprint,
        "external_hardware_used": report.external_hardware_used,
        "network_mutation": report.network_mutation,
        "notice": (
            "Default mode is a synthetic RX fixture. "
            "Use --hardware only with a physically connected RX-capable SoapySDR device."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
