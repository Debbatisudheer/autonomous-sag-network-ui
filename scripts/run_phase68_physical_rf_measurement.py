from __future__ import annotations

import argparse
import json

from sag_network.physical_rf import (
    PhysicalRfEvidence,
    PhysicalRfMeasurementEngine,
)
from sag_network.physical_sdr import (
    PhysicalSdrConfig,
    PhysicalSdrSource,
    SoapySdrRxBackend,
    SyntheticPhysicalSdrBackend,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 68 physical RF measurement")
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
        evidence = PhysicalRfEvidence.HARDWARE_MEASUREMENT
    else:
        source = PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6800))
        evidence = PhysicalRfEvidence.SYNTHETIC_FIXTURE

    capture = source.capture(config, timestamp_s=68.0)
    report = PhysicalRfMeasurementEngine().measure(
        capture=capture,
        evidence_class=evidence,
        external_hardware_used=source.external_hardware_used,
    )
    print(json.dumps({
        "name": "Physical RF Measurement",
        "phase": "68",
        "status": "pass",
        "evidence_class": report.evidence_class.value,
        "sample_count": report.sample_count,
        "sample_rate_hz": report.sample_rate_hz,
        "center_frequency_hz": report.center_frequency_hz,
        "channel": report.channel,
        "mean_power_normalized": report.mean_power_normalized,
        "rms_amplitude": report.rms_amplitude,
        "peak_amplitude": report.peak_amplitude,
        "crest_factor": report.crest_factor,
        "noise_power_normalized": report.noise_power_normalized,
        "signal_power_normalized": report.signal_power_normalized,
        "snr_db_estimate": report.snr_db_estimate,
        "dynamic_range_db": report.dynamic_range_db,
        "dc_offset_magnitude": report.dc_offset_magnitude,
        "sample_fingerprint": report.sample_fingerprint,
        "measurement_fingerprint": report.measurement_fingerprint,
        "external_hardware_used": report.external_hardware_used,
        "network_mutation": report.network_mutation,
        "notice": (
            "Normalized digital I/Q measurements only; calibrated dBm requires a receiver calibration chain. "
            "Default mode is a synthetic RX fixture. Use --hardware only with a physically connected RX-capable SoapySDR device."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
