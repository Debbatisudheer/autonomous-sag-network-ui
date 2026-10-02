from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport


class CrossDomainSAGEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    PUBLIC_DATA = "PUBLIC DATA"
    PUBLIC_EPHEMERIS = "PUBLIC EPHEMERIS"
    LOCAL_NETWORK_TEST = "LOCAL NETWORK TEST"


class CrossDomainSAGConfig(BaseModel):
    """Deterministic configuration for Ground-Air-Space integration."""

    reference_time_s: float = Field(ge=0)
    user_demand_bps: dict[str, float] = Field(default_factory=dict)
    use_udp_loopback: bool = False
    timeout_s: float = Field(gt=0, le=10.0)
    use_real_ephemeris: bool = False

    @model_validator(mode="after")
    def validate_demands(self) -> CrossDomainSAGConfig:
        if any(value < 0 for value in self.user_demand_bps.values()):
            raise ValueError("user_demand_bps values must be non-negative")
        return self


class CrossDomainSAGSummary(BaseModel):
    """Cross-domain coverage, association, and telemetry summary."""

    total_user_count: int = Field(ge=0)
    associated_user_count: int = Field(ge=0)
    unassociated_user_count: int = Field(ge=0)
    total_demand_bps: float = Field(ge=0)
    total_allocated_capacity_bps: float = Field(ge=0)
    unmet_demand_bps: float = Field(ge=0)
    total_candidate_count: int = Field(ge=0)
    available_candidate_count: int = Field(ge=0)
    ground_candidate_count: int = Field(ge=0)
    air_candidate_count: int = Field(ge=0)
    space_candidate_count: int = Field(ge=0)
    selected_ground_count: int = Field(ge=0)
    selected_air_count: int = Field(ge=0)
    selected_space_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    mean_link_margin_db: float
    mean_sinr_db: float
    mean_propagation_delay_ms: float
    mean_doppler_shift_hz: float
    mean_air_remaining_energy_wh: float = Field(ge=0)
    telemetry_sample_count: int = Field(ge=0)
    stale_telemetry_sample_count: int = Field(ge=0)
    latest_telemetry_timestamp_s: float = Field(ge=0)


class CrossDomainSAGIntegrationReport(BaseModel):
    """Auditable Ground-Air-Space integration result."""

    phase: str = "76"
    status: str = "pass"
    evidence_class: CrossDomainSAGEvidence
    telemetry_loop: NetworkTelemetryLoopReport
    unified_snapshot: UnifiedNetworkSnapshot
    summary: CrossDomainSAGSummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    source_sha256: str = ""
    provenance_verified: bool = False
    propagation_model: str = Field(min_length=1)
    ephemeris_source: str = Field(min_length=1)
    external_network_used: bool = False
    network_mutation: bool = False
    hardware_measurement: bool = False


__all__ = [
    "CrossDomainSAGEvidence",
    "CrossDomainSAGConfig",
    "CrossDomainSAGSummary",
    "CrossDomainSAGIntegrationReport",
]
