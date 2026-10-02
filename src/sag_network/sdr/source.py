from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Protocol

from sag_network.sdr.models import SdrFrame, SdrLoopbackConfig, SdrSampleBlock


class SdrSampleSource(Protocol):
    def capture(self, frame: SdrFrame, config: SdrLoopbackConfig, timestamp_s: float) -> SdrSampleBlock:
        """Capture IQ samples for one frame."""


class SyntheticSdrSource:
    """Deterministic software IQ source used when SDR hardware is unavailable."""

    def __init__(self, *, seed: int = 4300) -> None:
        self.seed = seed

    def capture(
        self, frame: SdrFrame, config: SdrLoopbackConfig, timestamp_s: float
    ) -> SdrSampleBlock:
        sample_rate = config.symbol_rate_hz * config.samples_per_symbol
        rng = random.Random(self.seed + len(frame.bits))
        i_samples: list[float] = []
        q_samples: list[float] = []
        phase_step = 2.0 * math.pi * config.carrier_offset_hz / sample_rate
        for bit_index, bit in enumerate(frame.bits):
            symbol = 1.0 if bit else -1.0
            for sample_index in range(config.samples_per_symbol):
                index = bit_index * config.samples_per_symbol + sample_index
                phase = config.phase_offset_rad + phase_step * index
                noise_i = rng.gauss(0.0, config.noise_std)
                noise_q = rng.gauss(0.0, config.noise_std)
                i_samples.append(symbol * math.cos(phase) + noise_i)
                q_samples.append(symbol * math.sin(phase) + noise_q)
        return SdrSampleBlock(
            timestamp_s=timestamp_s,
            sample_rate_hz=sample_rate,
            center_frequency_hz=0.0,
            i_samples=i_samples,
            q_samples=q_samples,
        )


class CsvSdrSource:
    """Reads an IQ capture from a CSV file with `i` and `q` columns."""

    def __init__(
        self,
        path: Path,
        *,
        sample_rate_hz: float,
        center_frequency_hz: float = 0.0,
    ) -> None:
        self.path = path
        self.sample_rate_hz = sample_rate_hz
        self.center_frequency_hz = center_frequency_hz

    def capture(
        self, frame: SdrFrame, config: SdrLoopbackConfig, timestamp_s: float
    ) -> SdrSampleBlock:
        del frame, config
        i_samples: list[float] = []
        q_samples: list[float] = []
        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "i" not in reader.fieldnames or "q" not in reader.fieldnames:
                raise ValueError("IQ CSV must contain i and q columns")
            for row in reader:
                i_samples.append(float(row["i"]))
                q_samples.append(float(row["q"]))
        return SdrSampleBlock(
            timestamp_s=timestamp_s,
            sample_rate_hz=self.sample_rate_hz,
            center_frequency_hz=self.center_frequency_hz,
            i_samples=i_samples,
            q_samples=q_samples,
        )


__all__ = ["CsvSdrSource", "SdrSampleSource", "SyntheticSdrSource"]
