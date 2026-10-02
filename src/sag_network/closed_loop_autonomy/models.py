from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.cross_domain_sag.models import CrossDomainSAGEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.domain.unified_handover import UnifiedHandoverEventType
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport


class AutonomyAction(str, Enum):
    ATTACH = "attach"
    RETAIN = "retain"
    HANDOVER = "handover"
    NO_COVERAGE = "no_coverage"
    BLOCKED = "blocked"


class ClosedLoopAutonomyConfig(BaseModel):
    """Deterministic control-loop boundaries for autonomous SAG operation."""

    timestamps_s: list[float] = Field(min_length=1)
    user_demand_bps: dict[str, float] = Field(default_factory=dict)
    use_real_ephemeris: bool = False
    use_udp_loopback: bool = False
    timeout_s: float = Field(gt=0, le=10.0)
    minimum_telemetry_health: float = Field(default=0.75, ge=0, le=1)
    handover_hysteresis_db: float = Field(default=2.0, ge=0)
    handover_time_to_trigger_s: float = Field(default=5.0, ge=0)

    @model_validator(mode="after")
    def validate_timestamps(self) -> ClosedLoopAutonomyConfig:
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


class AutonomyCycleResult(BaseModel):
    """One observe-decide-act-verify cycle for one user."""

    timestamp_s: float = Field(ge=0)
    user_id: str = Field(min_length=1)
    previous_resource_id: str | None = None
    previous_domain: NetworkDomain | None = None
    selected_resource_id: str | None = None
    selected_domain: NetworkDomain | None = None
    best_available_resource_id: str | None = None
    best_available_domain: NetworkDomain | None = None
    best_link_margin_db: float | None = None
    selected_capacity_bps: float = Field(ge=0)
    demand_bps: float = Field(ge=0)
    demand_satisfied: bool
    telemetry_health: float = Field(ge=0, le=1)
    telemetry_gate_open: bool
    decision_action: AutonomyAction
    handover_event_type: UnifiedHandoverEventType
    decision_reason: str = Field(min_length=1)
    verification_passed: bool
    verification_reason: str = Field(min_length=1)


class ClosedLoopAutonomySummary(BaseModel):
    """Aggregate control-loop evidence."""

    cycle_count: int = Field(ge=0)
    user_count: int = Field(ge=0)
    associated_cycle_count: int = Field(ge=0)
    handover_count: int = Field(ge=0)
    attach_count: int = Field(ge=0)
    retain_count: int = Field(ge=0)
    no_coverage_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    verification_pass_count: int = Field(ge=0)
    verification_fail_count: int = Field(ge=0)
    telemetry_health_mean: float = Field(ge=0, le=1)
    demand_satisfaction_ratio: float = Field(ge=0, le=1)
    autonomous_action_rate: float = Field(ge=0, le=1)
    final_serving_users: int = Field(ge=0)


class ClosedLoopAutonomyReport(BaseModel):
    """Auditable Phase 77 closed-loop autonomy result."""

    phase: str = "77"
    status: str = "pass"
    evidence_class: CrossDomainSAGEvidence
    telemetry_loop: NetworkTelemetryLoopReport
    cycles: list[AutonomyCycleResult]
    summary: ClosedLoopAutonomySummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    source_sha256: str = ""
    provenance_verified: bool = False
    propagation_model: str = Field(min_length=1)
    ephemeris_source: str = Field(min_length=1)
    external_network_used: bool = False
    network_mutation: bool = False
    hardware_measurement: bool = False


__all__ = [
    "AutonomyAction",
    "AutonomyCycleResult",
    "ClosedLoopAutonomyConfig",
    "ClosedLoopAutonomyReport",
    "ClosedLoopAutonomySummary",
]
