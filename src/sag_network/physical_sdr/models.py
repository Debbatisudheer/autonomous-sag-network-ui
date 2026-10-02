from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PhysicalSdrEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    HARDWARE_MEASUREMENT = "HARDWARE MEASUREMENT"


class PhysicalSdrConfig(BaseModel):
    device_args: str = ""
    channel: int = Field(ge=0, le=63)
    sample_rate_hz: float = Field(gt=0)
    center_frequency_hz: float = Field(ge=0)
    bandwidth_hz: float | None = Field(default=None, gt=0)
    gain_db: float | None = None
    antenna: str | None = None
    sample_count: int = Field(gt=0, le=1_000_000)
    timeout_us: int = Field(gt=0, le=10_000_000)


class PhysicalSdrCapture(BaseModel):
    timestamp_s: float = Field(ge=0)
    sample_rate_hz: float = Field(gt=0)
    center_frequency_hz: float = Field(ge=0)
    channel: int = Field(ge=0, le=63)
    i_samples: list[float] = Field(min_length=1)
    q_samples: list[float] = Field(min_length=1)
    hardware_device: str = Field(min_length=1)


class PhysicalSdrDeviceInfo(BaseModel):
    driver: str
    hardware: str
    serial: str = ""
    label: str = ""
    args: str = ""


class PhysicalSdrReport(BaseModel):
    timestamp_s: float = Field(ge=0)
    sample_count: int = Field(gt=0)
    sample_rate_hz: float = Field(gt=0)
    center_frequency_hz: float = Field(ge=0)
    channel: int = Field(ge=0, le=63)
    mean_i: float
    mean_q: float
    mean_power: float = Field(ge=0)
    iq_imbalance_ratio: float = Field(ge=0)
    sample_fingerprint: str = Field(min_length=64, max_length=64)
    processing_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_class: PhysicalSdrEvidence
    external_hardware_used: bool
    network_mutation: bool


__all__ = [
    "PhysicalSdrCapture",
    "PhysicalSdrConfig",
    "PhysicalSdrDeviceInfo",
    "PhysicalSdrEvidence",
    "PhysicalSdrReport",
]
