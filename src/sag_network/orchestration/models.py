from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class OrchestrationDecision(str, Enum):
    KEEP = "keep"
    PLACE = "place"
    REBALANCE = "rebalance"
    REJECT = "reject"


class OrchestrationWorkload(BaseModel):
    workload_id: str = Field(min_length=1)
    cpu_millicores: int = Field(gt=0)
    memory_mb: int = Field(gt=0)
    priority: int = Field(ge=0, le=100)
    preferred_node_id: str | None = None
    anti_affinity_group: str | None = None


class OrchestrationNode(BaseModel):
    node_id: str = Field(min_length=1)
    cpu_capacity_millicores: int = Field(gt=0)
    memory_capacity_mb: int = Field(gt=0)
    cpu_used_millicores: int = Field(default=0, ge=0)
    memory_used_mb: int = Field(default=0, ge=0)
    healthy: bool = True

    @model_validator(mode="after")
    def validate_usage(self) -> OrchestrationNode:
        if self.cpu_used_millicores > self.cpu_capacity_millicores:
            raise ValueError("cpu usage cannot exceed capacity")
        if self.memory_used_mb > self.memory_capacity_mb:
            raise ValueError("memory usage cannot exceed capacity")
        return self


class OrchestrationPlacement(BaseModel):
    workload_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    decision: OrchestrationDecision
    cpu_headroom_millicores: int = Field(ge=0)
    memory_headroom_mb: int = Field(ge=0)
    placement_score: float
    rationale: str = Field(min_length=1)


class OrchestrationReport(BaseModel):
    timestamp_s: float = Field(ge=0)
    placements: list[OrchestrationPlacement] = Field(default_factory=list)
    rejected_workload_ids: list[str] = Field(default_factory=list)
    moved_workload_ids: list[str] = Field(default_factory=list)
    utilization_before: float = Field(ge=0, le=1)
    utilization_after: float = Field(ge=0, le=1)
    rebalance_required: bool
    plan_fingerprint: str = Field(min_length=64, max_length=64)


__all__ = [
    "OrchestrationDecision",
    "OrchestrationNode",
    "OrchestrationPlacement",
    "OrchestrationReport",
    "OrchestrationWorkload",
]
