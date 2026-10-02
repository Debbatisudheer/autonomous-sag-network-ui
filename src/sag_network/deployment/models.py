from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DeploymentStatus(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    REJECTED = "rejected"


class RuntimeHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class EdgeRuntimeConfig(BaseModel):
    """Deterministic resource and liveness policy for one edge runtime."""

    runtime_id: str = Field(min_length=1)
    cpu_limit_millicores: int = Field(default=1000, ge=1)
    memory_limit_mb: int = Field(default=1024, ge=1)
    maximum_concurrent_tasks: int = Field(default=8, ge=1)
    health_timeout_s: float = Field(default=5.0, gt=0)
    degraded_cpu_ratio: float = Field(default=0.85, gt=0, le=1)
    degraded_memory_ratio: float = Field(default=0.85, gt=0, le=1)


class EdgeWorkload(BaseModel):
    """One deployable deterministic workload admitted by the edge runtime."""

    workload_id: str = Field(min_length=1)
    cpu_millicores: int = Field(ge=1)
    memory_mb: int = Field(ge=1)
    latency_budget_ms: float = Field(gt=0)
    priority: int = Field(default=0, ge=0, le=100)


class WorkloadAdmission(BaseModel):
    workload_id: str = Field(min_length=1)
    admitted: bool
    reason: str = Field(min_length=1)
    cpu_headroom_millicores: int = Field(ge=0)
    memory_headroom_mb: int = Field(ge=0)


class RuntimeHealthReport(BaseModel):
    runtime_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    status: RuntimeHealth
    cpu_utilization_ratio: float = Field(ge=0, le=1)
    memory_utilization_ratio: float = Field(ge=0, le=1)
    active_workloads: int = Field(ge=0)
    liveness: bool
    readiness: bool
    deterministic_fingerprint: str = Field(min_length=64, max_length=64)


class EdgeDeploymentReport(BaseModel):
    """Offline deployment-harness result; no external process is started."""

    runtime_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    status: DeploymentStatus
    admissions: list[WorkloadAdmission]
    health: RuntimeHealthReport
    admitted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    deployment_fingerprint: str = Field(min_length=64, max_length=64)
    external_process_started: bool = False

    @model_validator(mode="after")
    def validate_counts(self) -> EdgeDeploymentReport:
        if self.admitted_count + self.rejected_count != len(self.admissions):
            raise ValueError("admission counts must equal admission records")
        if self.external_process_started:
            raise ValueError("Phase 40 offline harness must not start external processes")
        return self


__all__ = [
    "DeploymentStatus",
    "EdgeDeploymentReport",
    "EdgeRuntimeConfig",
    "EdgeWorkload",
    "RuntimeHealth",
    "RuntimeHealthReport",
    "WorkloadAdmission",
]
