from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NetworkLoopEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    PUBLIC_DATA = "PUBLIC DATA"
    LOCAL_NETWORK_TEST = "LOCAL NETWORK TEST"


class NetworkTelemetryEnvelope(BaseModel):
    record_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    sequence: int = Field(ge=0)
    source_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    quality: str = Field(min_length=1)


class NetworkTelemetryLoopReport(BaseModel):
    name: str = "Real Network Telemetry Loop"
    phase: str = "70"
    status: str
    evidence_class: NetworkLoopEvidence
    source_sha256: str
    provenance_verified: bool
    input_record_count: int = Field(ge=0)
    transmitted_record_count: int = Field(ge=0)
    received_record_count: int = Field(ge=0)
    accepted_record_count: int = Field(ge=0)
    rejected_record_count: int = Field(ge=0)
    state_sample_count: int = Field(ge=0)
    delivered_record_rate: float = Field(ge=0.0, le=1.0)
    loopback_latency_ms: float = Field(ge=0.0)
    transport: str = Field(min_length=1)
    external_network_used: bool
    network_mutation: bool
    loop_fingerprint: str = Field(min_length=64, max_length=64)
