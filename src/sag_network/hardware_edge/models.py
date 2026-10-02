from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class HardwareEdgeEvidence(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"
    LOCAL_HOST_MEASUREMENT = "LOCAL HOST MEASUREMENT"


class EdgeDeviceProfile(BaseModel):
    """Deploy-time resource envelope and observed host identity for one edge target."""

    device_id: str = Field(min_length=1)
    target_class: str = Field(min_length=1)
    operating_system: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    cpu_count: int = Field(ge=1)
    memory_limit_mb: int = Field(ge=1)
    storage_limit_mb: int = Field(ge=1)
    observed_hardware: bool = False


class EdgeWorkloadSpec(BaseModel):
    """Bounded telemetry-processing workload intended for edge execution."""

    workload_id: str = Field(min_length=1)
    max_cpu_time_ms: float = Field(gt=0)
    max_python_heap_kb: int = Field(ge=1)
    max_wall_time_ms: float = Field(gt=0)
    maximum_input_records: int = Field(default=1024, ge=1)


class EdgeTelemetrySummary(BaseModel):
    """Deterministic compact state summary produced by the deployed workload."""

    input_record_count: int = Field(ge=0)
    source_ids: list[str]
    mean_value: float
    minimum_value: float
    maximum_value: float
    latest_timestamp_s: float = Field(ge=0)


class EdgeWorkloadExecution(BaseModel):
    workload_id: str = Field(min_length=1)
    accepted: bool
    completed: bool
    input_record_count: int = Field(ge=0)
    cpu_time_ms: float = Field(ge=0)
    wall_time_ms: float = Field(ge=0)
    peak_python_heap_kb: int = Field(ge=0)
    within_cpu_budget: bool
    within_wall_budget: bool
    within_heap_budget: bool
    output_fingerprint: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=1)


class HardwareEdgeDeploymentReport(BaseModel):
    """Auditable deployment-and-execution result with explicit evidence class."""

    phase: str = "71"
    status: str = "pass"
    evidence_class: HardwareEdgeEvidence
    device: EdgeDeviceProfile
    workload: EdgeWorkloadExecution
    telemetry_summary: EdgeTelemetrySummary
    deployment_fingerprint: str = Field(min_length=64, max_length=64)
    external_network_used: bool = False
    network_mutation: bool = False

    @model_validator(mode="after")
    def validate_flags(self) -> HardwareEdgeDeploymentReport:
        if self.external_network_used or self.network_mutation:
            raise ValueError("Phase 71 local deployment path must not use external network or mutate it")
        return self


__all__ = [
    "EdgeDeviceProfile",
    "EdgeTelemetrySummary",
    "EdgeWorkloadExecution",
    "EdgeWorkloadSpec",
    "HardwareEdgeDeploymentReport",
    "HardwareEdgeEvidence",
]
