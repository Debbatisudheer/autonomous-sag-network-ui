from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PhysicalWirelessEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    HARDWARE_MEASUREMENT = "HARDWARE MEASUREMENT"


class PhysicalWirelessLinkConfig(BaseModel):
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)
    payload: bytes = Field(min_length=1, max_length=1024)
    sample_rate_hz: float = Field(gt=0.0)
    symbol_rate_hz: float = Field(gt=0.0)
    amplitude: float = Field(gt=0.0, le=1.0)
    decision_threshold: float = Field(gt=0.0, le=1.0)
    preamble_bytes: bytes = Field(default=b"\xAA\xAA\xAA\xAA", min_length=1, max_length=16)

    @property
    def samples_per_symbol(self) -> int:
        value = self.sample_rate_hz / self.symbol_rate_hz
        rounded = round(value)
        if abs(value - rounded) > 1e-9 or rounded < 2:
            raise ValueError("sample_rate_hz / symbol_rate_hz must be an integer >= 2")
        return rounded


class PhysicalWirelessFrame(BaseModel):
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)
    payload: bytes = Field(min_length=1)
    encoded_bytes: bytes = Field(min_length=1)
    bit_count: int = Field(gt=0)
    crc32_hex: str = Field(min_length=8, max_length=8)


class PhysicalWirelessLinkReport(BaseModel):
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)
    payload_bytes: int = Field(gt=0)
    encoded_bytes: int = Field(gt=0)
    transmitted_bit_count: int = Field(gt=0)
    received_bit_count: int = Field(ge=0)
    received_bits: int = Field(ge=0)
    bit_errors: int = Field(ge=0)
    bit_error_rate: float = Field(ge=0.0, le=1.0)
    delivered: bool
    crc_valid: bool
    sample_count: int = Field(gt=0)
    sample_rate_hz: float = Field(gt=0.0)
    symbol_rate_hz: float = Field(gt=0.0)
    sample_fingerprint: str = Field(min_length=64, max_length=64)
    link_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_class: PhysicalWirelessEvidence
    external_hardware_used: bool
    network_mutation: bool


__all__ = [
    "PhysicalWirelessEvidence",
    "PhysicalWirelessFrame",
    "PhysicalWirelessLinkConfig",
    "PhysicalWirelessLinkReport",
]
