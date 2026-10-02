from __future__ import annotations

import json

from sag_network.hil import HardwareInTheLoopEngine, HardwareLoopConfig, VirtualHardwareDevice
from sag_network.sdr import SdrFrame, SdrLoopbackConfig, SyntheticSdrSource


def main() -> None:
    frame = SdrFrame(frame_id="phase44-frame-1", bits=[1, 0, 1, 1, 0, 0, 1, 0])
    sdr_config = SdrLoopbackConfig(
        symbol_rate_hz=1000.0,
        samples_per_symbol=8,
        carrier_offset_hz=37.5,
        phase_offset_rad=0.31,
        noise_std=0.01,
    )
    hardware_config = HardwareLoopConfig(
        device_id="virtual-rf-frontend-44",
        gain=0.98,
        adc_bits=12,
        adc_full_scale=2.0,
        deterministic_noise_std=0.003,
        processing_delay_samples=4,
    )
    report = HardwareInTheLoopEngine().process(
        frame=frame,
        sdr_config=sdr_config,
        source=SyntheticSdrSource(seed=4400),
        hardware_config=hardware_config,
        device=VirtualHardwareDevice(seed=4400),
        timestamp_s=44.0,
    )
    if report.decoded_frame_count != 1 or report.total_bit_errors != 0:
        raise RuntimeError("phase 44 hardware-in-the-loop validation failed")
    print(json.dumps({
        "name": "Hardware-in-the-Loop",
        "phase": "44",
        "status": "pass",
        "device_id": report.device_id,
        "cycle_count": report.cycle_count,
        "input_sample_count": report.input_sample_count,
        "output_sample_count": report.output_sample_count,
        "decoded_frame_count": report.decoded_frame_count,
        "bit_errors": report.total_bit_errors,
        "ber": report.ber,
        "snr_db": report.snr_db,
        "clipping_count": report.clipping_count,
        "processing_delay_samples": report.processing_delay_samples,
        "sample_fingerprint": report.sample_fingerprint,
        "processing_fingerprint": report.processing_fingerprint,
        "external_hardware_used": report.external_hardware_used,
        "network_mutation": report.network_mutation,
        "fixture": "synthetic offline hardware-in-the-loop fixture",
    }, indent=2))


if __name__ == "__main__":
    main()
