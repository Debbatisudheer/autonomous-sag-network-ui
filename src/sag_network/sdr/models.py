from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class SdrSampleBlock(BaseModel):
    timestamp_s: float = Field(ge=0)
    sample_rate_hz: float = Field(gt=0)
    center_frequency_hz: float = Field(ge=0)
    i_samples: list[float] = Field(min_length=1)
    q_samples: list[float] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_lengths(self) -> SdrSampleBlock:
        if len(self.i_samples) != len(self.q_samples):
            raise ValueError("I and Q sample counts must match")
        return self


class SdrFrame(BaseModel):
    frame_id: str = Field(min_length=1)
    bits: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bits(self) -> SdrFrame:
        if any(bit not in (0, 1) for bit in self.bits):
            raise ValueError("frame bits must be binary")
        return self


class SdrLoopbackConfig(BaseModel):
    symbol_rate_hz: float = Field(gt=0)
    samples_per_symbol: int = Field(ge=1, le=1024)
    carrier_offset_hz: float = 0.0
    phase_offset_rad: float = 0.0
    noise_std: float = Field(ge=0, le=10)

    @model_validator(mode="after")
    def validate_sample_rate(self) -> SdrLoopbackConfig:
        if self.symbol_rate_hz * self.samples_per_symbol <= 0:
            raise ValueError("derived sample rate must be positive")
        return self


class SdrFrameStatus(str, Enum):
    DECODED = "decoded"
    REJECTED = "rejected"


class SdrDecodeResult(BaseModel):
    frame_id: str = Field(min_length=1)
    status: SdrFrameStatus
    decoded_bits: list[int] = Field(min_length=1)
    bit_errors: int = Field(ge=0)
    ber: float = Field(ge=0, le=1)
    signal_power: float = Field(ge=0)
    noise_power: float = Field(ge=0)
    snr_db: float
    estimated_frequency_offset_hz: float


class SdrLoopbackReport(BaseModel):
    timestamp_s: float = Field(ge=0)
    sample_count: int = Field(gt=0)
    frame_count: int = Field(gt=0)
    decoded_frame_count: int = Field(ge=0)
    total_bit_errors: int = Field(ge=0)
    mean_ber: float = Field(ge=0, le=1)
    mean_snr_db: float
    estimated_frequency_offset_hz: float
    sample_fingerprint: str = Field(min_length=64, max_length=64)
    processing_fingerprint: str = Field(min_length=64, max_length=64)
    external_hardware_used: bool
    network_mutation: bool


__all__ = [
    "SdrDecodeResult",
    "SdrFrame",
    "SdrFrameStatus",
    "SdrLoopbackConfig",
    "SdrLoopbackReport",
    "SdrSampleBlock",
]
