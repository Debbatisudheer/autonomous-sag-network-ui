from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class HardwareLoopConfig(BaseModel):
    device_id: str = Field(min_length=1)
    gain: float = Field(gt=0, le=4)
    adc_bits: int = Field(ge=8, le=24)
    adc_full_scale: float = Field(gt=0)
    deterministic_noise_std: float = Field(ge=0, le=1)
    processing_delay_samples: int = Field(ge=0, le=1024)

    @model_validator(mode="after")
    def validate_quantizer(self) -> HardwareLoopConfig:
        levels = (2**self.adc_bits) - 1
        if levels <= 0:
            raise ValueError("ADC quantizer must have at least two levels")
        return self


class HardwareExchangeResult(BaseModel):
    device_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    input_sample_count: int = Field(gt=0)
    output_sample_count: int = Field(gt=0)
    clipping_count: int = Field(ge=0)
    processing_delay_samples: int = Field(ge=0)
    external_hardware_used: bool


class HardwareInTheLoopReport(BaseModel):
    timestamp_s: float = Field(ge=0)
    device_id: str = Field(min_length=1)
    cycle_count: int = Field(gt=0)
    input_sample_count: int = Field(gt=0)
    output_sample_count: int = Field(gt=0)
    decoded_frame_count: int = Field(ge=0)
    total_bit_errors: int = Field(ge=0)
    ber: float = Field(ge=0, le=1)
    snr_db: float
    clipping_count: int = Field(ge=0)
    processing_delay_samples: int = Field(ge=0)
    sample_fingerprint: str = Field(min_length=64, max_length=64)
    processing_fingerprint: str = Field(min_length=64, max_length=64)
    external_hardware_used: bool
    network_mutation: bool


__all__ = [
    "HardwareExchangeResult",
    "HardwareInTheLoopReport",
    "HardwareLoopConfig",
]
