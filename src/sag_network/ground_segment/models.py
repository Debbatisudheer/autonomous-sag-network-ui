from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.ground import GroundNetworkSnapshot
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport


class GroundSegmentEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    PUBLIC_DATA = "PUBLIC DATA"
    LOCAL_NETWORK_TEST = "LOCAL NETWORK TEST"


class GroundSegmentConfig(BaseModel):
    """Deterministic configuration for ground-segment telemetry integration."""

    reference_time_s: float = Field(ge=0)
    user_demand_bps: dict[str, float] = Field(default_factory=dict)
    use_udp_loopback: bool = False
    timeout_s: float = Field(gt=0, le=10.0)


class GroundSegmentSummary(BaseModel):
    """Compact ground-segment operational summary derived from the integrated state."""

    active_cell_count: int = Field(ge=0)
    total_cell_count: int = Field(ge=0)
    associated_user_count: int = Field(ge=0)
    unassociated_user_count: int = Field(ge=0)
    total_demand_bps: float = Field(ge=0)
    total_allocated_capacity_bps: float = Field(ge=0)
    mean_link_margin_db: float
    mean_sinr_db: float
    telemetry_sample_count: int = Field(ge=0)
    stale_telemetry_sample_count: int = Field(ge=0)
    latest_telemetry_timestamp_s: float = Field(ge=0)


class GroundSegmentIntegrationReport(BaseModel):
    """Auditable ground-segment integration result."""

    phase: str = "73"
    status: str = "pass"
    evidence_class: GroundSegmentEvidence
    telemetry_loop: NetworkTelemetryLoopReport
    ground_snapshot: GroundNetworkSnapshot
    summary: GroundSegmentSummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    external_network_used: bool = False
    network_mutation: bool = False
