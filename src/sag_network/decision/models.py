from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import NetworkDomain, UnifiedNetworkSnapshot
from sag_network.predictive.models import WarningSeverity


class DecisionActionType(str, Enum):
    """Action proposals understood by the deterministic decision baseline."""

    NO_ACTION = "no_action"
    PREPARE_HANDOVER = "prepare_handover"
    RESERVE_SPECTRUM = "reserve_spectrum"
    REROUTE_FLOW = "reroute_flow"
    REDUCE_LOAD = "reduce_load"
    PREPOSITION_RESOURCE = "preposition_resource"


class DecisionStatus(str, Enum):
    """Decision-engine outcome for one evaluated policy cycle."""

    NO_ACTION_REQUIRED = "no_action_required"
    ACTION_SELECTED = "action_selected"
    ACTION_UNAVAILABLE = "action_unavailable"


class DecisionPriority(str, Enum):
    """Operational priority assigned to a selected or proposed action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionConfig(BaseModel):
    """Deterministic policy boundaries for the explainable decision baseline."""

    minimum_confidence: float = Field(default=0.5, ge=0, le=1)
    minimum_alternative_margin_db: float = Field(default=1.0, ge=0)
    minimum_alternative_capacity_ratio: float = Field(default=0.5, ge=0, le=1)
    maximum_resource_utilization_ratio: float = Field(default=0.9, ge=0, le=1)
    handover_domain_change_penalty: float = Field(default=0.05, ge=0, le=1)
    maximum_actions: int = Field(default=10, ge=1)


class DecisionEvidence(BaseModel):
    """Machine-readable evidence supporting an action proposal."""

    warning_source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: str = Field(min_length=1)
    severity: WarningSeverity
    predicted_value: float
    threshold_value: float
    lead_time_s: float = Field(ge=0)
    confidence_score: float = Field(ge=0, le=1)
    threshold_direction: str = Field(min_length=1)


class DecisionAction(BaseModel):
    """One feasible or infeasible action proposal produced by the policy layer."""

    action_type: DecisionActionType
    target_source_id: str = Field(min_length=1)
    target_resource_id: str | None = None
    alternative_resource_id: str | None = None
    target_domain: NetworkDomain | None = None
    alternative_domain: NetworkDomain | None = None
    feasible: bool
    utility_score: float = Field(ge=0)
    priority: DecisionPriority
    rationale: str = Field(min_length=1)
    evidence: list[DecisionEvidence] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class SelectedDecision(BaseModel):
    """Selected decision plus its explainable supporting evidence."""

    action: DecisionAction
    decision_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    status: DecisionStatus
    confidence_score: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1)


class DecisionReport(BaseModel):
    """Complete decision-engine output for one predictive network state."""

    timestamp_s: float = Field(ge=0)
    status: DecisionStatus
    selected_decisions: list[SelectedDecision] = Field(default_factory=list)
    candidate_actions: list[DecisionAction] = Field(default_factory=list)
    predictive_warning_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_selection_count(self) -> DecisionReport:
        if len(self.selected_decisions) > len(self.candidate_actions):
            raise ValueError("selected decisions cannot exceed candidate actions")
        return self


def decision_context_snapshot(
    *,
    network_snapshot: UnifiedNetworkSnapshot,
    scheduling_snapshot: SpectrumSchedulingSnapshot | None,
) -> tuple[UnifiedNetworkSnapshot, SpectrumSchedulingSnapshot | None]:
    """Return an explicit typed context tuple for downstream policy adapters."""
    return network_snapshot, scheduling_snapshot


__all__ = [
    "DecisionAction",
    "DecisionActionType",
    "DecisionConfig",
    "DecisionEvidence",
    "DecisionPriority",
    "DecisionReport",
    "DecisionStatus",
    "SelectedDecision",
    "decision_context_snapshot",
]
