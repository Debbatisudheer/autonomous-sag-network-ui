from __future__ import annotations

import random
from typing import Protocol

from sag_network.hil.models import HardwareExchangeResult, HardwareLoopConfig
from sag_network.sdr.models import SdrSampleBlock


class HardwareDevice(Protocol):
    def exchange(
        self, block: SdrSampleBlock, config: HardwareLoopConfig, sequence: int
    ) -> tuple[SdrSampleBlock, HardwareExchangeResult]:
        """Exchange one IQ block with a hardware-compatible device boundary."""


class VirtualHardwareDevice:
    """Deterministic software model of an ADC/RF device for offline HIL validation."""

    def __init__(self, *, seed: int = 4400) -> None:
        self.seed = seed

    def exchange(
        self, block: SdrSampleBlock, config: HardwareLoopConfig, sequence: int
    ) -> tuple[SdrSampleBlock, HardwareExchangeResult]:
        rng = random.Random(self.seed + sequence)
        quantization_levels = (2**config.adc_bits) - 1
        half_scale = config.adc_full_scale
        step = (2.0 * half_scale) / quantization_levels
        i_samples: list[float] = []
        q_samples: list[float] = []
        clipping_count = 0
        for i_value, q_value in zip(block.i_samples, block.q_samples):
            scaled_i = i_value * config.gain + rng.gauss(0.0, config.deterministic_noise_std)
            scaled_q = q_value * config.gain + rng.gauss(0.0, config.deterministic_noise_std)
            clipped_i = max(-half_scale, min(half_scale, scaled_i))
            clipped_q = max(-half_scale, min(half_scale, scaled_q))
            clipping_count += int(clipped_i != scaled_i) + int(clipped_q != scaled_q)
            i_samples.append(round(clipped_i / step) * step)
            q_samples.append(round(clipped_q / step) * step)
        output = SdrSampleBlock(
            timestamp_s=block.timestamp_s,
            sample_rate_hz=block.sample_rate_hz,
            center_frequency_hz=block.center_frequency_hz,
            i_samples=i_samples,
            q_samples=q_samples,
        )
        result = HardwareExchangeResult(
            device_id=config.device_id,
            sequence=sequence,
            input_sample_count=len(block.i_samples),
            output_sample_count=len(output.i_samples),
            clipping_count=clipping_count,
            processing_delay_samples=config.processing_delay_samples,
            external_hardware_used=False,
        )
        return output, result


__all__ = ["HardwareDevice", "VirtualHardwareDevice"]
