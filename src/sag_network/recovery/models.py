from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import NetworkDomain, UnifiedNetworkSnapshot
from sag_network.optimization.models import ControlState


class FailureType(str, Enum):
    """Failure categories detectable from synchronized SAG state."""

    NODE_FAILURE = "node_failure"
    LINK_FAILURE = "link_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CAPACITY_EXHAUSTION = "capacity_exhaustion"
    ROUTE_FAILURE = "route_failure"
    HANDOVER_FAILURE = "handover_failure"
    TELEMETRY_STALE = "telemetry_stale"
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    """Operational severity of a detected failure condition."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FailureStatus(str, Enum):
    """Lifecycle state of one diagnosed failure."""

    DETECTED = "detected"
    DIAGNOSED = "diagnosed"
    RECOVERY_PLANNED = "recovery_planned"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    UNRECOVERABLE = "unrecoverable"


class RootCause(str, Enum):
    """Deterministic root-cause categories used by diagnosis."""

    RESOURCE_UNAVAILABLE = "resource_unavailable"
    LINK_QUALITY_DEGRADED = "link_quality_degraded"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    TELEMETRY_STALE = "telemetry_stale"
    CONTROL_ACTION_FAILED = "control_action_failed"
    ROUTE_UNAVAILABLE = "route_unavailable"
    UNKNOWN = "unknown"


class RecoveryActionType(str, Enum):
    """Self-healing operations supported by the simulation recovery plane."""

    PREPARE_HANDOVER = "prepare_handover"
    REROUTE_FLOW = "reroute_flow"
    RESERVE_SPECTRUM = "reserve_spectrum"
    RELEASE_RESERVATION = "release_reservation"
    REDUCE_LOAD = "reduce_load"
    PREPOSITION_RESOURCE = "preposition_resource"
    REFRESH_TELEMETRY = "refresh_telemetry"


class RecoveryConfig(BaseModel):
    """Bounds for failure detection, recovery planning, and retry behavior."""

    stale_sample_limit: int = Field(default=1, ge=1)
    maximum_resource_utilization_ratio: float = Field(default=0.98, ge=0, le=1)
    minimum_remaining_capacity_bps: float = Field(default=1.0, ge=0)
    maximum_recovery_actions: int = Field(default=5, ge=1)
    maximum_recovery_attempts: int = Field(default=2, ge=1)
    minimum_alternative_margin_db: float = Field(default=0.0, ge=0)
    minimum_alternative_capacity_bps: float = Field(default=1.0, ge=0)
    load_reduction_ratio: float = Field(default=0.2, gt=0, le=1)
    require_available_alternative: bool = True


class FailureEvidence(BaseModel):
    """Machine-readable observation supporting a detected failure."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain | None = None
    metric: str = Field(min_length=1)
    observed_value: float | None = None
    threshold_value: float | None = None
    timestamp_s: float = Field(ge=0)
    age_s: float | None = Field(default=None, ge=0)
    details: str = Field(min_length=1)


class FailureEvent(BaseModel):
    """One deterministic failure event emitted by the detector."""

    event_id: str = Field(min_length=1)
    failure_type: FailureType
    source_id: str = Field(min_length=1)
    resource_id: str | None = None
    domain: NetworkDomain | None = None
    timestamp_s: float = Field(ge=0)
    severity: FailureSeverity
    confidence_score: float = Field(ge=0, le=1)
    status: FailureStatus = FailureStatus.DETECTED
    symptoms: list[str] = Field(default_factory=list)
    evidence: list[FailureEvidence] = Field(default_factory=list)


class FailureDiagnosis(BaseModel):
    """Diagnosis connecting observed symptoms to a deterministic root cause."""

    event_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    root_cause: RootCause
    confidence_score: float = Field(ge=0, le=1)
    contributing_symptoms: list[str] = Field(default_factory=list)
    recommended_action_types: list[RecoveryActionType] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class RecoveryAction(BaseModel):
    """One candidate self-healing action."""

    event_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    action_type: RecoveryActionType
    source_id: str = Field(min_length=1)
    target_resource_id: str | None = None
    alternative_resource_id: str | None = None
    target_domain: NetworkDomain | None = None
    alternative_domain: NetworkDomain | None = None
    timestamp_s: float = Field(ge=0)
    feasible: bool
    expected_recovery_score: float = Field(ge=0)
    rationale: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


class RecoveryPlan(BaseModel):
    """Bounded recovery plan for the currently open failures."""

    timestamp_s: float = Field(ge=0)
    event_ids: list[str] = Field(default_factory=list)
    candidate_actions: list[RecoveryAction] = Field(default_factory=list)
    selected_actions: list[RecoveryAction] = Field(default_factory=list)
    unresolved_event_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_selection(self) -> RecoveryPlan:
        candidate_ids = {action.action_id for action in self.candidate_actions}
        selected_ids = {action.action_id for action in self.selected_actions}
        if not selected_ids.issubset(candidate_ids):
            raise ValueError("selected recovery actions must come from candidate actions")
        if len(selected_ids) != len(self.selected_actions):
            raise ValueError("selected recovery action ids must be unique")
        return self


class RecoveryExecutionResult(BaseModel):
    """Application and verification outcome of one recovery action."""

    action_id: str = Field(min_length=1)
    status: FailureStatus
    applied: bool
    verified: bool
    reason: str = Field(min_length=1)


class SelfHealingState(BaseModel):
    """Versioned state of currently known and recovered failure events."""

    timestamp_s: float = Field(ge=0)
    version: int = Field(default=0, ge=0)
    active_event_ids: list[str] = Field(default_factory=list)
    recovered_event_ids: list[str] = Field(default_factory=list)
    attempt_counts: dict[str, int] = Field(default_factory=dict)
    refresh_requests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_collections(self) -> SelfHealingState:
        if len(self.active_event_ids) != len(set(self.active_event_ids)):
            raise ValueError("active_event_ids must be unique")
        if len(self.recovered_event_ids) != len(set(self.recovered_event_ids)):
            raise ValueError("recovered_event_ids must be unique")
        if any(value < 0 for value in self.attempt_counts.values()):
            raise ValueError("attempt counts cannot be negative")
        return self


class FailureRecoveryReport(BaseModel):
    """Complete detect-diagnose-plan-recover report for one simulation instant."""

    timestamp_s: float = Field(ge=0)
    detected_failures: list[FailureEvent] = Field(default_factory=list)
    diagnoses: list[FailureDiagnosis] = Field(default_factory=list)
    plan: RecoveryPlan
    execution_results: list[RecoveryExecutionResult] = Field(default_factory=list)
    self_healing_state: SelfHealingState
    resulting_control_state: ControlState | None = None
    all_recovered: bool

    @model_validator(mode="after")
    def validate_timestamps(self) -> FailureRecoveryReport:
        if (
            self.plan.timestamp_s != self.timestamp_s
            or self.self_healing_state.timestamp_s != self.timestamp_s
        ):
            raise ValueError("recovery timestamps must match report timestamp")
        return self


def recovery_context_snapshot(
    *,
    network_snapshot: UnifiedNetworkSnapshot,
    scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    control_state: ControlState | None,
) -> tuple[UnifiedNetworkSnapshot, SpectrumSchedulingSnapshot | None, ControlState | None]:
    """Return a typed recovery context for downstream adapters."""
    return network_snapshot, scheduling_snapshot, control_state


__all__ = [
    "FailureDiagnosis",
    "FailureEvent",
    "FailureEvidence",
    "FailureRecoveryReport",
    "FailureSeverity",
    "FailureStatus",
    "FailureType",
    "RecoveryAction",
    "RecoveryActionType",
    "RecoveryConfig",
    "RecoveryExecutionResult",
    "RecoveryPlan",
    "RootCause",
    "SelfHealingState",
    "recovery_context_snapshot",
]
