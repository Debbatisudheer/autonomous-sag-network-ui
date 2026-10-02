from __future__ import annotations

import pytest

from sag_network.hil import (
    HardwareInTheLoopEngine,
    HardwareLoopConfig,
    VirtualHardwareDevice,
)
from sag_network.sdr import SdrFrame, SdrLoopbackConfig, SyntheticSdrSource


def frame() -> SdrFrame:
    return SdrFrame(frame_id="f44", bits=[1, 0, 1, 1, 0, 0, 1, 0])


def sdr_config() -> SdrLoopbackConfig:
    return SdrLoopbackConfig(
        symbol_rate_hz=1000.0,
        samples_per_symbol=8,
        carrier_offset_hz=37.5,
        phase_offset_rad=0.31,
        noise_std=0.01,
    )


def hardware_config() -> HardwareLoopConfig:
    return HardwareLoopConfig(
        device_id="virtual-rf-frontend-44",
        gain=0.98,
        adc_bits=12,
        adc_full_scale=2.0,
        deterministic_noise_std=0.003,
        processing_delay_samples=4,
    )


def run() -> object:
    return HardwareInTheLoopEngine().process(
        frame=frame(),
        sdr_config=sdr_config(),
        source=SyntheticSdrSource(seed=4400),
        hardware_config=hardware_config(),
        device=VirtualHardwareDevice(seed=4400),
        timestamp_s=44.0,
    )


def test_virtual_hardware_loop_decodes_without_errors() -> None:
    report = run()
    assert report.decoded_frame_count == 1
    assert report.total_bit_errors == 0
    assert report.ber == 0.0
    assert report.external_hardware_used is False
    assert report.network_mutation is False


def test_hardware_metadata_is_preserved() -> None:
    report = run()
    assert report.device_id == "virtual-rf-frontend-44"
    assert report.input_sample_count == 64
    assert report.output_sample_count == 64
    assert report.processing_delay_samples == 4


def test_hardware_processing_is_deterministic() -> None:
    first = run()
    second = run()
    assert first.sample_fingerprint == second.sample_fingerprint
    assert first.processing_fingerprint == second.processing_fingerprint


def test_device_gain_affects_processing_fingerprint() -> None:
    first = run()
    altered = hardware_config().model_copy(update={"gain": 0.9})
    second = HardwareInTheLoopEngine().process(
        frame=frame(),
        sdr_config=sdr_config(),
        source=SyntheticSdrSource(seed=4400),
        hardware_config=altered,
        device=VirtualHardwareDevice(seed=4400),
        timestamp_s=44.0,
    )
    assert first.processing_fingerprint != second.processing_fingerprint


def test_adc_clipping_is_reported() -> None:
    clipped = hardware_config().model_copy(update={"gain": 4.0, "adc_full_scale": 0.5})
    report = HardwareInTheLoopEngine().process(
        frame=frame(),
        sdr_config=sdr_config(),
        source=SyntheticSdrSource(seed=4400),
        hardware_config=clipped,
        device=VirtualHardwareDevice(seed=4400),
        timestamp_s=44.0,
    )
    assert report.clipping_count > 0


def test_device_id_is_required() -> None:
    with pytest.raises(ValueError):
        HardwareLoopConfig(
            device_id="",
            gain=1.0,
            adc_bits=12,
            adc_full_scale=2.0,
            deterministic_noise_std=0.0,
            processing_delay_samples=0,
        )


def test_adc_bits_are_bounded() -> None:
    with pytest.raises(ValueError):
        HardwareLoopConfig(
            device_id="rf",
            gain=1.0,
            adc_bits=7,
            adc_full_scale=2.0,
            deterministic_noise_std=0.0,
            processing_delay_samples=0,
        )


def test_noise_is_bounded() -> None:
    with pytest.raises(ValueError):
        HardwareLoopConfig(
            device_id="rf",
            gain=1.0,
            adc_bits=12,
            adc_full_scale=2.0,
            deterministic_noise_std=1.1,
            processing_delay_samples=0,
        )


def test_virtual_device_output_has_matching_iq_lengths() -> None:
    report = run()
    assert report.input_sample_count == report.output_sample_count


def test_network_state_is_not_mutated() -> None:
    assert run().network_mutation is False
