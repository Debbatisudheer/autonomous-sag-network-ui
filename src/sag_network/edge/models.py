from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.decision.models import DecisionPriority
from sag_network.domain.unified import NetworkDomain


class EdgeNodeType(str, Enum):
    GROUND_EDGE = "ground_edge"
    AIR_EDGE = "air_edge"
    SPACE_EDGE = "space_edge"
    REGIONAL_CONTROLLER = "regional_controller"
    CENTRAL_CONTROLLER = "central_controller"


class EdgeNodeHealth(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class EdgeCapability(str, Enum):
    TELEMETRY_INGESTION = "telemetry_ingestion"
    STATE_AGGREGATION = "state_aggregation"
    PREDICTION = "prediction"
    DECISION = "decision"
    OPTIMIZATION = "optimization"
    RECOVERY = "recovery"
    DIGITAL_TWIN_SYNC = "digital_twin_sync"


class DistributedTaskType(str, Enum):
    TELEMETRY_INGESTION = "telemetry_ingestion"
    STATE_AGGREGATION = "state_aggregation"
    PREDICTION = "prediction"
    DECISION = "decision"
    OPTIMIZATION = "optimization"
    RECOVERY = "recovery"
    DIGITAL_TWIN_SYNC = "digital_twin_sync"


class DistributedTask(BaseModel):
    """One workload unit scheduled across the distributed SAG compute fabric."""

    task_id: str = Field(min_length=1)
    task_type: DistributedTaskType
    source_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    priority: DecisionPriority
    required_capabilities: list[EdgeCapability] = Field(default_factory=list)
    preferred_domain: NetworkDomain | None = None
    cpu_required_millicores: int = Field(default=100, ge=1)
    memory_required_mb: int = Field(default=128, ge=1)
    expected_processing_ms: float = Field(default=1.0, gt=0)
    maximum_latency_ms: float = Field(default=100.0, gt=0)
    payload_hash: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_capabilities(self) -> DistributedTask:
        if len(self.required_capabilities) != len(set(self.required_capabilities)):
            raise ValueError("required_capabilities must be unique")
        return self


class EdgeNode(BaseModel):
    """A logical distributed compute node for edge, regional, or central execution."""

    node_id: str = Field(min_length=1)
    node_type: EdgeNodeType
    domain: NetworkDomain | None = None
    capabilities: list[EdgeCapability] = Field(default_factory=list)
    cpu_capacity_millicores: int = Field(default=1000, ge=1)
    memory_capacity_mb: int = Field(default=1024, ge=1)
    queue_capacity: int = Field(default=100, ge=1)
    processing_latency_ms: float = Field(default=1.0, gt=0)
    network_latency_ms: float = Field(default=1.0, ge=0)
    cpu_load_ratio: float = Field(default=0.0, ge=0, le=1)
    memory_load_ratio: float = Field(default=0.0, ge=0, le=1)
    queued_tasks: int = Field(default=0, ge=0)
    health: EdgeNodeHealth = EdgeNodeHealth.ONLINE
    active: bool = True

    @model_validator(mode="after")
    def validate_capabilities_and_queue(self) -> EdgeNode:
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("capabilities must be unique")
        if self.queued_tasks > self.queue_capacity:
            raise ValueError("queued_tasks must not exceed queue_capacity")
        if not self.active or self.health is EdgeNodeHealth.OFFLINE:
            return self
        return self


class EdgeLink(BaseModel):
    """Deterministic logical connectivity between distributed compute nodes."""

    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    latency_ms: float = Field(ge=0)
    bandwidth_mbps: float = Field(gt=0)
    active: bool = True

    @model_validator(mode="after")
    def validate_distinct_nodes(self) -> EdgeLink:
        if self.source_node_id == self.target_node_id:
            raise ValueError("edge link endpoints must differ")
        return self


class EdgeFabricSnapshot(BaseModel):
    """Point-in-time distributed compute-fabric state."""

    timestamp_s: float = Field(ge=0)
    nodes: list[EdgeNode]
    links: list[EdgeLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> EdgeFabricSnapshot:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("edge node ids must be unique")
        link_keys = [(link.source_node_id, link.target_node_id) for link in self.links]
        if len(link_keys) != len(set(link_keys)):
            raise ValueError("edge link pairs must be unique")
        known = set(node_ids)
        if any(link.source_node_id not in known or link.target_node_id not in known for link in self.links):
            raise ValueError("edge links must reference known nodes")
        return self


class TaskPlacement(BaseModel):
    """Deterministic placement decision for one distributed task."""

    task_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    feasible: bool
    estimated_latency_ms: float = Field(ge=0)
    cpu_headroom_millicores: int = Field(ge=0)
    memory_headroom_mb: int = Field(ge=0)
    placement_score: float = Field(ge=0)
    rationale: str = Field(min_length=1)


class DistributedTaskResult(BaseModel):
    """Execution outcome for one distributed task assignment."""

    task_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    accepted: bool
    completed: bool
    timestamp_s: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    reason: str = Field(min_length=1)


class StateReplica(BaseModel):
    """Versioned state replica used for deterministic distributed convergence."""

    state_key: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    version: int = Field(ge=0)
    state_hash: str = Field(min_length=64, max_length=64)


class DistributedStateConfig(BaseModel):
    """Boundaries for replicated distributed state."""

    history_limit: int = Field(default=1000, ge=1)
    enforce_monotonic_version: bool = True
    enforce_monotonic_timestamp: bool = True


class DistributedArchitectureConfig(BaseModel):
    """Control-plane bounds for deterministic distributed orchestration."""

    maximum_tasks_per_cycle: int = Field(default=20, ge=1)
    maximum_task_latency_ms: float = Field(default=100.0, gt=0)
    maximum_node_cpu_load_ratio: float = Field(default=0.9, ge=0, le=1)
    maximum_node_memory_load_ratio: float = Field(default=0.9, ge=0, le=1)
    state_config: DistributedStateConfig = Field(default_factory=DistributedStateConfig)


class DistributedCycleReport(BaseModel):
    """Result of one distributed orchestration cycle."""

    timestamp_s: float = Field(ge=0)
    placements: list[TaskPlacement] = Field(default_factory=list)
    results: list[DistributedTaskResult] = Field(default_factory=list)
    replicated_state_count: int = Field(ge=0)
    rejected_task_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_tasks(self) -> DistributedCycleReport:
        placement_ids = {item.task_id for item in self.placements}
        if not all(result.task_id in placement_ids for result in self.results):
            raise ValueError("task results must reference placements")
        if len(self.rejected_task_ids) != len(set(self.rejected_task_ids)):
            raise ValueError("rejected_task_ids must be unique")
        return self


__all__ = [
    "DistributedArchitectureConfig",
    "DistributedCycleReport",
    "DistributedStateConfig",
    "DistributedTask",
    "DistributedTaskResult",
    "DistributedTaskType",
    "EdgeCapability",
    "EdgeFabricSnapshot",
    "EdgeLink",
    "EdgeNode",
    "EdgeNodeHealth",
    "EdgeNodeType",
    "StateReplica",
    "TaskPlacement",
]
