from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PhysicalRfEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    HARDWARE_MEASUREMENT = "HARDWARE MEASUREMENT"


class PhysicalRfMeasurementConfig(BaseModel):
    noise_floor_fraction: float = Field(gt=0.0, lt=1.0)
    min_noise_power: float = Field(gt=0.0)


class PhysicalRfReport(BaseModel):
    timestamp_s: float = Field(ge=0.0)
    sample_count: int = Field(gt=0)
    sample_rate_hz: float = Field(gt=0.0)
    center_frequency_hz: float = Field(ge=0.0)
    channel: int = Field(ge=0, le=63)
    mean_i: float
    mean_q: float
    dc_offset_magnitude: float = Field(ge=0.0)
    mean_power_normalized: float = Field(ge=0.0)
    rms_amplitude: float = Field(ge=0.0)
    peak_amplitude: float = Field(ge=0.0)
    crest_factor: float = Field(ge=0.0)
    noise_power_normalized: float = Field(ge=0.0)
    signal_power_normalized: float = Field(ge=0.0)
    snr_db_estimate: float
    dynamic_range_db: float
    sample_fingerprint: str = Field(min_length=64, max_length=64)
    measurement_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_class: PhysicalRfEvidence
    external_hardware_used: bool
    network_mutation: bool


__all__ = [
    "PhysicalRfEvidence",
    "PhysicalRfMeasurementConfig",
    "PhysicalRfReport",
]
