from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class SpectrumResource(BaseModel):
    """Configurable shared spectrum pool for one access resource."""

    resource_id: str = Field(min_length=1)
    bandwidth_hz: float = Field(gt=0)
    resource_block_bandwidth_hz: float = Field(gt=0)
    scheduler_efficiency: float = Field(gt=0, le=1.0)

    @model_validator(mode="after")
    def validate_bandwidth_partition(self) -> SpectrumResource:
        if self.resource_block_bandwidth_hz > self.bandwidth_hz:
            raise ValueError("resource_block_bandwidth_hz must not exceed bandwidth_hz")
        if self.total_resource_blocks < 1:
            raise ValueError("spectrum resource must contain at least one resource block")
        return self

    @property
    def total_resource_blocks(self) -> int:
        return int(self.bandwidth_hz // self.resource_block_bandwidth_hz)


class SpectrumAllocationRequest(BaseModel):
    """One traffic flow's access-spectrum request."""

    flow_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    requested_bps: float = Field(ge=0)
    minimum_throughput_bps: float = Field(ge=0)
    priority: int = Field(ge=0, le=100)


class SpectrumAllocation(BaseModel):
    """Result of discrete resource-block allocation for one flow."""

    flow_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    admitted: bool
    resource_id: str | None = None
    requested_bps: float = Field(ge=0)
    required_bps: float = Field(ge=0)
    allocated_bps: float = Field(ge=0)
    resource_blocks: int = Field(ge=0)
    allocated_bandwidth_hz: float = Field(ge=0)
    reason: str = Field(min_length=1)


class ResourceUtilization(BaseModel):
    """Current occupancy of one shared spectrum pool."""

    resource_id: str = Field(min_length=1)
    total_resource_blocks: int = Field(ge=1)
    used_resource_blocks: int = Field(ge=0)
    free_resource_blocks: int = Field(ge=0)
    utilization_ratio: float = Field(ge=0, le=1)
    scheduled_capacity_bps: float = Field(ge=0)
    remaining_capacity_bps: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> ResourceUtilization:
        if self.used_resource_blocks + self.free_resource_blocks != self.total_resource_blocks:
            raise ValueError("resource block counts must reconcile")
        return self


class SpectrumSchedulingSnapshot(BaseModel):
    """Deterministic access-spectrum scheduling result at one simulation instant."""

    timestamp_s: float = Field(ge=0)
    allocations: list[SpectrumAllocation]
    utilization: list[ResourceUtilization]
