from __future__ import annotations

import json

from sag_network.sdr import (
    SdrFrame,
    SdrInTheLoopEngine,
    SdrLoopbackConfig,
    SyntheticSdrSource,
)


def main() -> None:
    frame = SdrFrame(frame_id="phase43-frame-1", bits=[1, 0, 1, 1, 0, 0, 1, 0])
    config = SdrLoopbackConfig(
        symbol_rate_hz=1000.0,
        samples_per_symbol=8,
        carrier_offset_hz=37.5,
        phase_offset_rad=0.31,
        noise_std=0.02,
    )
    report = SdrInTheLoopEngine().process(
        frame=frame,
        config=config,
        source=SyntheticSdrSource(seed=4300),
        timestamp_s=43.0,
    )
    if report.decoded_frame_count != 1 or report.total_bit_errors != 0:
        raise RuntimeError("phase 43 SDR loopback validation failed")
    print(json.dumps({
        "name": "SDR-in-the-Loop",
        "phase": "43",
        "status": "pass",
        "sample_count": report.sample_count,
        "frame_count": report.frame_count,
        "decoded_frame_count": report.decoded_frame_count,
        "bit_errors": report.total_bit_errors,
        "ber": report.mean_ber,
        "snr_db": report.mean_snr_db,
        "estimated_frequency_offset_hz": report.estimated_frequency_offset_hz,
        "sample_fingerprint": report.sample_fingerprint,
        "processing_fingerprint": report.processing_fingerprint,
        "external_hardware_used": report.external_hardware_used,
        "network_mutation": report.network_mutation,
        "fixture": "synthetic offline SDR IQ loopback fixture",
    }, indent=2))


if __name__ == "__main__":
    main()
