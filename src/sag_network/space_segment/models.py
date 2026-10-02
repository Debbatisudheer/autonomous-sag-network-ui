from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport
from sag_network.space.selection import SatelliteCandidate


class SpaceSegmentEvidence(StrEnum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    PUBLIC_DATA = "PUBLIC DATA"
    PUBLIC_EPHEMERIS = "PUBLIC EPHEMERIS"
    LOCAL_NETWORK_TEST = "LOCAL NETWORK TEST"


class SpaceSegmentConfig(BaseModel):
    reference_time_s: float = Field(ge=0)
    user_demand_bps: dict[str, float] = Field(default_factory=dict)
    use_udp_loopback: bool = False
    timeout_s: float = Field(gt=0, le=10.0)
    use_real_ephemeris: bool = False
    simulation_epoch_timestamp_s: float = Field(default=0.0, ge=0)


class SpaceUserAssociation(BaseModel):
    user_id: str = Field(min_length=1)
    demand_bps: float = Field(ge=0)
    selected_satellite_id: str | None = None
    allocated_capacity_bps: float = Field(ge=0)
    candidates: list[SatelliteCandidate]


class SpaceSegmentSummary(BaseModel):
    active_satellite_count: int = Field(ge=0)
    total_satellite_count: int = Field(ge=0)
    associated_user_count: int = Field(ge=0)
    unassociated_user_count: int = Field(ge=0)
    total_demand_bps: float = Field(ge=0)
    total_allocated_capacity_bps: float = Field(ge=0)
    mean_link_margin_db: float
    mean_sinr_db: float
    mean_elevation_deg: float
    mean_propagation_delay_ms: float
    mean_doppler_shift_hz: float
    telemetry_sample_count: int = Field(ge=0)
    stale_telemetry_sample_count: int = Field(ge=0)
    latest_telemetry_timestamp_s: float = Field(ge=0)
    propagation_model: str = Field(min_length=1)
    ephemeris_source: str = Field(min_length=1)


class SpaceSegmentSnapshot(BaseModel):
    timestamp_s: float = Field(ge=0)
    associations: list[SpaceUserAssociation]


class SpaceSegmentIntegrationReport(BaseModel):
    phase: str = "75"
    status: str = "pass"
    evidence_class: SpaceSegmentEvidence
    telemetry_loop: NetworkTelemetryLoopReport
    space_snapshot: SpaceSegmentSnapshot
    summary: SpaceSegmentSummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    source_sha256: str = ""
    provenance_verified: bool = False
    external_network_used: bool = False
    network_mutation: bool = False
    hardware_measurement: bool = False
