from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.decision.models import DecisionPriority
from sag_network.domain.unified import NetworkDomain, UnifiedNetworkSnapshot


class OptimizationObjective(str, Enum):
    """Primary optimization objective used by the deterministic baseline."""

    BALANCED_UTILITY = "balanced_utility"
    MAXIMIZE_CAPACITY = "maximize_capacity"
    MAXIMIZE_LINK_MARGIN = "maximize_link_margin"
    MINIMIZE_LATENCY = "minimize_latency"
    BALANCE_RESOURCES = "balance_resources"


class ControlActionType(str, Enum):
    """Abstract actuation operations supported by the simulation control plane."""

    PREPARE_HANDOVER = "prepare_handover"
    RESERVE_SPECTRUM = "reserve_spectrum"
    REROUTE_FLOW = "reroute_flow"
    REDUCE_LOAD = "reduce_load"
    PREPOSITION_RESOURCE = "preposition_resource"
    NO_ACTION = "no_action"


class ControlActionStatus(str, Enum):
    """Execution state of one simulated control action."""

    PLANNED = "planned"
    APPLIED = "applied"
    REJECTED = "rejected"
    VERIFIED = "verified"
    FAILED = "failed"


class OptimizationConfig(BaseModel):
    """Boundaries and weights for deterministic constrained optimization."""

    objective: OptimizationObjective = OptimizationObjective.BALANCED_UTILITY
    maximum_actions: int = Field(default=5, ge=1)
    minimum_expected_gain: float = Field(default=0.0, ge=0)
    priority_weight: float = Field(default=1.0, ge=0)
    decision_utility_weight: float = Field(default=1.0, ge=0)
    capacity_gain_weight: float = Field(default=0.5, ge=0)
    margin_gain_weight: float = Field(default=0.5, ge=0)
    latency_gain_weight: float = Field(default=0.5, ge=0)
    resource_balance_weight: float = Field(default=0.25, ge=0)
    switching_cost: float = Field(default=0.1, ge=0)
    domain_change_cost: float = Field(default=0.1, ge=0)
    maximum_resource_utilization_ratio: float = Field(default=0.9, ge=0, le=1)
    minimum_capacity_ratio: float = Field(default=0.5, ge=0, le=1)
    load_reduction_ratio: float = Field(default=0.1, gt=0, le=1)


class ControlState(BaseModel):
    """Mutable simulation-side control state derived from network state."""

    timestamp_s: float = Field(ge=0)
    version: int = Field(default=0, ge=0)
    selected_resources: dict[str, str] = Field(default_factory=dict)
    prepared_handover_targets: dict[str, str] = Field(default_factory=dict)
    reserved_resource_ids: list[str] = Field(default_factory=list)
    rerouted_sources: dict[str, str] = Field(default_factory=dict)
    load_reduction_ratios: dict[str, float] = Field(default_factory=dict)
    prepositioned_resource_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_collections(self) -> ControlState:
        if len(self.reserved_resource_ids) != len(set(self.reserved_resource_ids)):
            raise ValueError("reserved_resource_ids must be unique")
        if len(self.prepositioned_resource_ids) != len(set(self.prepositioned_resource_ids)):
            raise ValueError("prepositioned_resource_ids must be unique")
        return self

    @classmethod
    def from_network_snapshot(cls, snapshot: UnifiedNetworkSnapshot) -> ControlState:
        selected: dict[str, str] = {
            association.user_id: association.selected_resource_id
            for association in snapshot.associations
            if association.selected_resource_id is not None
        }
        return cls(timestamp_s=snapshot.timestamp_s, selected_resources=selected)


class ControlAction(BaseModel):
    """One optimized control action before or after simulated execution."""

    action_id: str = Field(min_length=1)
    action_type: ControlActionType
    source_id: str = Field(min_length=1)
    target_resource_id: str | None = None
    alternative_resource_id: str | None = None
    target_domain: NetworkDomain | None = None
    alternative_domain: NetworkDomain | None = None
    timestamp_s: float = Field(ge=0)
    feasible: bool
    priority: DecisionPriority
    decision_utility: float = Field(ge=0)
    expected_gain: float = Field(ge=0)
    objective_score: float = Field(ge=0)
    rationale: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    load_reduction_ratio: float = Field(default=0.1, gt=0, le=1)
    status: ControlActionStatus = ControlActionStatus.PLANNED


class OptimizationPlan(BaseModel):
    """Constrained optimized control plan produced for one network instant."""

    timestamp_s: float = Field(ge=0)
    objective: OptimizationObjective
    objective_value: float = Field(ge=0)
    candidate_actions: list[ControlAction] = Field(default_factory=list)
    selected_actions: list[ControlAction] = Field(default_factory=list)
    rejected_action_ids: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_selection(self) -> OptimizationPlan:
        candidate_ids = {item.action_id for item in self.candidate_actions}
        selected_ids = {item.action_id for item in self.selected_actions}
        if not selected_ids.issubset(candidate_ids):
            raise ValueError("selected actions must come from candidate actions")
        if len(selected_ids) != len(self.selected_actions):
            raise ValueError("selected action ids must be unique")
        return self


class ControlExecutionResult(BaseModel):
    """Execution and verification result for one optimized action."""

    action_id: str = Field(min_length=1)
    status: ControlActionStatus
    applied: bool
    verified: bool
    reason: str = Field(min_length=1)


class ControlExecutionReport(BaseModel):
    """Closed-loop actuation outcome including the resulting simulation state."""

    timestamp_s: float = Field(ge=0)
    results: list[ControlExecutionResult] = Field(default_factory=list)
    resulting_state: ControlState
    all_verified: bool


class OptimizationReport(BaseModel):
    """Combined optimization and control report for one autonomous cycle."""

    timestamp_s: float = Field(ge=0)
    plan: OptimizationPlan
    execution: ControlExecutionReport

    @model_validator(mode="after")
    def validate_timestamps(self) -> OptimizationReport:
        if self.plan.timestamp_s != self.timestamp_s or (
            self.execution.timestamp_s != self.timestamp_s
        ):
            raise ValueError("optimization and execution timestamps must match report timestamp")
        return self


__all__ = [
    "ControlAction",
    "ControlActionStatus",
    "ControlActionType",
    "ControlExecutionReport",
    "ControlExecutionResult",
    "ControlState",
    "OptimizationConfig",
    "OptimizationObjective",
    "OptimizationPlan",
    "OptimizationReport",
]
