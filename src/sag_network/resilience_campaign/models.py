from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.cross_domain_sag.models import CrossDomainSAGEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport


class ResilienceFailureMode(str, Enum):
    """Deterministic injected fault families used by Phase 78."""

    RESOURCE_OUTAGE = "resource_outage"
    DOMAIN_OUTAGE = "domain_outage"
    TELEMETRY_DEGRADATION = "telemetry_degradation"
    CAPACITY_DEGRADATION = "capacity_degradation"
    CASCADING_OUTAGE = "cascading_outage"


class ResilienceCampaignConfig(BaseModel):
    """Bounded deterministic configuration for the Phase 78 campaign."""

    timestamps_s: list[float] = Field(min_length=2)
    user_demand_bps: dict[str, float] = Field(default_factory=dict)
    use_real_ephemeris: bool = False
    use_udp_loopback: bool = False
    timeout_s: float = Field(gt=0, le=10.0)
    minimum_telemetry_health: float = Field(default=0.75, ge=0, le=1)
    handover_hysteresis_db: float = Field(default=2.0, ge=0)
    handover_time_to_trigger_s: float = Field(default=5.0, ge=0)

    @model_validator(mode="after")
    def validate_campaign_inputs(self) -> ResilienceCampaignConfig:
        if any(timestamp < 0 for timestamp in self.timestamps_s):
            raise ValueError("timestamps_s must contain non-negative values")
        if any(
            right < left
            for left, right in zip(self.timestamps_s, self.timestamps_s[1:], strict=False)
        ):
            raise ValueError("timestamps_s must be non-decreasing")
        if any(value < 0 for value in self.user_demand_bps.values()):
            raise ValueError("user_demand_bps values must be non-negative")
        return self

    model_config = {"validate_assignment": True}


class ResilienceScenario(BaseModel):
    """One deterministic failure-injection interval."""

    scenario_id: str = Field(min_length=1, max_length=128)
    failure_mode: ResilienceFailureMode
    start_time_s: float = Field(ge=0)
    end_time_s: float = Field(gt=0)
    affected_resource_ids: tuple[str, ...] = ()
    affected_domains: tuple[NetworkDomain, ...] = ()
    telemetry_health: float | None = Field(default=None, ge=0, le=1)
    capacity_scale: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def validate_scenario(self) -> ResilienceScenario:
        if self.end_time_s <= self.start_time_s:
            raise ValueError("end_time_s must be greater than start_time_s")
        if len(set(self.affected_resource_ids)) != len(self.affected_resource_ids):
            raise ValueError("affected_resource_ids must be unique")
        if len(set(self.affected_domains)) != len(self.affected_domains):
            raise ValueError("affected_domains must be unique")
        if self.failure_mode is ResilienceFailureMode.RESOURCE_OUTAGE and not self.affected_resource_ids:
            raise ValueError("resource outage scenarios require affected_resource_ids")
        if self.failure_mode is ResilienceFailureMode.CASCADING_OUTAGE and not (
            self.affected_resource_ids or self.affected_domains
        ):
            raise ValueError(
                "cascading outage scenarios require affected_resource_ids or affected_domains"
            )
        if self.failure_mode is ResilienceFailureMode.DOMAIN_OUTAGE and not self.affected_domains:
            raise ValueError("domain outage scenarios require affected_domains")
        if (
            self.failure_mode is ResilienceFailureMode.TELEMETRY_DEGRADATION
            and self.telemetry_health is None
        ):
            raise ValueError("telemetry degradation scenarios require telemetry_health")
        if (
            self.failure_mode is ResilienceFailureMode.CAPACITY_DEGRADATION
            and self.capacity_scale is None
        ):
            raise ValueError("capacity degradation scenarios require capacity_scale")
        return self


class ResilienceCycleResult(BaseModel):
    """One observed autonomous control cycle under an injected fault."""

    scenario_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    user_id: str = Field(min_length=1)
    failure_active: bool
    previous_resource_id: str | None = None
    selected_resource_id: str | None = None
    selected_domain: NetworkDomain | None = None
    best_available_resource_id: str | None = None
    demand_bps: float = Field(ge=0)
    selected_capacity_bps: float = Field(ge=0)
    demand_satisfied: bool
    telemetry_health: float = Field(ge=0, le=1)
    telemetry_gate_open: bool
    decision_action: str = Field(min_length=1)
    decision_reason: str = Field(min_length=1)
    verification_passed: bool
    verification_reason: str = Field(min_length=1)


class ResilienceScenarioResult(BaseModel):
    """Measured campaign result for one fault scenario."""

    scenario_id: str = Field(min_length=1)
    failure_mode: ResilienceFailureMode
    start_time_s: float = Field(ge=0)
    end_time_s: float = Field(gt=0)
    cycle_count: int = Field(ge=0)
    affected_cycle_count: int = Field(ge=0)
    impacted_user_count: int = Field(ge=0)
    attach_count: int = Field(ge=0)
    handover_count: int = Field(ge=0)
    retain_count: int = Field(ge=0)
    no_coverage_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    verification_pass_count: int = Field(ge=0)
    verification_fail_count: int = Field(ge=0)
    demand_satisfaction_ratio: float = Field(ge=0, le=1)
    recovery_observed: bool
    recovery_time_s: float | None = Field(default=None, ge=0)
    recovery_latency_s: float | None = Field(default=None, ge=0)
    max_unmet_demand_bps: float = Field(ge=0)
    cycles: tuple[ResilienceCycleResult, ...] = Field(min_length=1)
    scenario_fingerprint: str = Field(min_length=64, max_length=64)


class ResilienceCampaignSummary(BaseModel):
    """Aggregate resilience measurements across the complete campaign."""

    scenario_count: int = Field(ge=1)
    cycle_count: int = Field(ge=0)
    affected_cycle_count: int = Field(ge=0)
    recovered_scenario_count: int = Field(ge=0)
    unrecovered_scenario_count: int = Field(ge=0)
    attach_count: int = Field(ge=0)
    handover_count: int = Field(ge=0)
    retain_count: int = Field(ge=0)
    no_coverage_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    verification_pass_count: int = Field(ge=0)
    verification_fail_count: int = Field(ge=0)
    demand_satisfaction_ratio: float = Field(ge=0, le=1)
    verification_success_ratio: float = Field(ge=0, le=1)
    mean_recovery_latency_s: float | None = Field(default=None, ge=0)
    max_recovery_latency_s: float | None = Field(default=None, ge=0)


class ResilienceCampaignReport(BaseModel):
    """Auditable Phase 78 resilience-campaign report."""

    phase: str = "78"
    status: str = "pass"
    name: str = "Real-World Resilience Campaign"
    evidence_class: CrossDomainSAGEvidence
    telemetry_loop: NetworkTelemetryLoopReport
    scenarios: tuple[ResilienceScenarioResult, ...] = Field(min_length=1)
    summary: ResilienceCampaignSummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    source_sha256: str = ""
    provenance_verified: bool = False
    propagation_model: str = Field(min_length=1)
    ephemeris_source: str = Field(min_length=1)
    external_network_used: bool = False
    network_mutation: bool = False
    hardware_measurement: bool = False
    failure_injection_is_simulated: bool = True


__all__ = [
    "ResilienceCampaignConfig",
    "ResilienceCampaignReport",
    "ResilienceCampaignSummary",
    "ResilienceCycleResult",
    "ResilienceFailureMode",
    "ResilienceScenario",
    "ResilienceScenarioResult",
]
