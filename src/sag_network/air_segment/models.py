from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.air import AirNetworkSnapshot
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport


class AirSegmentEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    PUBLIC_DATA = "PUBLIC DATA"
    LOCAL_NETWORK_TEST = "LOCAL NETWORK TEST"


class AirSegmentConfig(BaseModel):
    """Deterministic configuration for airborne-segment telemetry integration."""

    reference_time_s: float = Field(ge=0)
    user_demand_bps: dict[str, float] = Field(default_factory=dict)
    use_udp_loopback: bool = False
    timeout_s: float = Field(gt=0, le=10.0)


class AirSegmentSummary(BaseModel):
    """Compact airborne operational summary derived from integrated state."""

    active_platform_count: int = Field(ge=0)
    total_platform_count: int = Field(ge=0)
    associated_user_count: int = Field(ge=0)
    unassociated_user_count: int = Field(ge=0)
    total_demand_bps: float = Field(ge=0)
    total_allocated_capacity_bps: float = Field(ge=0)
    mean_link_margin_db: float
    mean_sinr_db: float
    mean_remaining_energy_wh: float = Field(ge=0)
    telemetry_sample_count: int = Field(ge=0)
    stale_telemetry_sample_count: int = Field(ge=0)
    latest_telemetry_timestamp_s: float = Field(ge=0)


class AirSegmentIntegrationReport(BaseModel):
    """Auditable airborne-segment integration result."""

    phase: str = "74"
    status: str = "pass"
    evidence_class: AirSegmentEvidence
    telemetry_loop: NetworkTelemetryLoopReport
    air_snapshot: AirNetworkSnapshot
    summary: AirSegmentSummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    external_network_used: bool = False
    network_mutation: bool = False
