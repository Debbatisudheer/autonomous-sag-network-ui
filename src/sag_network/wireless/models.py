from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class WirelessTransportKind(str, Enum):
    UDP = "udp"
    SYNTHETIC = "synthetic"


class WirelessPacket(BaseModel):
    sequence: int = Field(ge=0)
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)
    payload: bytes = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    checksum_hex: str = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def validate_checksum_shape(self) -> WirelessPacket:
        if any(character not in "0123456789abcdef" for character in self.checksum_hex):
            raise ValueError("checksum_hex must contain lowercase hexadecimal characters")
        return self


class WirelessExchange(BaseModel):
    sequence: int = Field(ge=0)
    bytes_sent: int = Field(ge=0)
    bytes_received: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    packet_loss: bool
    checksum_valid: bool
    transport: WirelessTransportKind
    external_network_used: bool


class WirelessIntegrationConfig(BaseModel):
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)
    payload: bytes = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    sequence: int = Field(ge=0)
    transport: WirelessTransportKind
    timeout_s: float = Field(gt=0, le=30)


class WirelessIntegrationReport(BaseModel):
    timestamp_s: float = Field(ge=0)
    sequence: int = Field(ge=0)
    transport: WirelessTransportKind
    bytes_sent: int = Field(ge=0)
    bytes_received: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    packet_loss: bool
    checksum_valid: bool
    delivered: bool
    packet_fingerprint: str = Field(min_length=64, max_length=64)
    exchange_fingerprint: str = Field(min_length=64, max_length=64)
    external_network_used: bool
    network_mutation: bool


__all__ = [
    "WirelessExchange",
    "WirelessIntegrationConfig",
    "WirelessIntegrationReport",
    "WirelessPacket",
    "WirelessTransportKind",
]
