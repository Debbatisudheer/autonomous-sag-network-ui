from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.hardware_edge.models import (
    HardwareEdgeDeploymentReport,
)
from sag_network.physical_sdr.models import PhysicalSdrReport
from sag_network.physical_wireless_link.models import PhysicalWirelessLinkReport


class HardwareSdrClosedLoopEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    PUBLIC_DATA = "PUBLIC DATA"
    LOCAL_HOST_MEASUREMENT = "LOCAL HOST MEASUREMENT"
    HARDWARE_MEASUREMENT = "HARDWARE MEASUREMENT"


class HardwareSdrClosedLoopConfig(BaseModel):
    sample_rate_hz: float = Field(gt=0.0)
    center_frequency_hz: float = Field(ge=0.0)
    symbol_rate_hz: float = Field(gt=0.0)
    amplitude: float = Field(gt=0.0, le=1.0)
    decision_threshold: float = Field(gt=0.0, le=1.0)
    sample_count: int = Field(gt=0, le=1_000_000)
    timeout_us: int = Field(gt=0, le=10_000_000)
    source_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)


class HardwareSdrClosedLoopReport(BaseModel):
    phase: str = "72"
    status: str = "pass"
    evidence_class: HardwareSdrClosedLoopEvidence
    edge: HardwareEdgeDeploymentReport
    sdr: PhysicalSdrReport
    wireless_link: PhysicalWirelessLinkReport
    control_payload_sha256: str = Field(min_length=64, max_length=64)
    loop_fingerprint: str = Field(min_length=64, max_length=64)
    hardware_sdr_used: bool = False
    external_network_used: bool = False
    network_mutation: bool = False


__all__ = [
    "HardwareSdrClosedLoopConfig",
    "HardwareSdrClosedLoopEvidence",
    "HardwareSdrClosedLoopReport",
]
