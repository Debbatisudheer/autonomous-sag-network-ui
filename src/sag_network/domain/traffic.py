from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ServiceClass(str, Enum):
    """Application classes represented by explicit, configurable QoS requirements."""

    CONVERSATIONAL = "conversational"
    INTERACTIVE = "interactive"
    STREAMING = "streaming"
    BEST_EFFORT = "best_effort"


class QoSProfile(BaseModel):
    """Service requirements used for deterministic traffic admission."""

    service_class: ServiceClass
    minimum_throughput_bps: float = Field(ge=0)
    maximum_latency_ms: float = Field(gt=0)
    maximum_loss_rate: float = Field(ge=0, lt=1)
    priority: int = Field(ge=0, le=100)


class TrafficDemand(BaseModel):
    """One flow's offered traffic demand at a simulation instant."""

    flow_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    demand_bps: float = Field(ge=0)
    qos: QoSProfile


class QoSMeasurement(BaseModel):
    """End-to-end service metrics available to the traffic admission layer."""

    capacity_bps: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    loss_rate: float = Field(ge=0, lt=1)


class TrafficAllocation(BaseModel):
    """Result of deterministic admission/allocation for one flow."""

    flow_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    admitted: bool
    requested_bps: float = Field(ge=0)
    allocated_bps: float = Field(ge=0)
    service_class: ServiceClass
    priority: int = Field(ge=0, le=100)
    resource_path: tuple[str, ...] = ()
    latency_ms: float | None = Field(default=None, ge=0)
    loss_rate: float | None = Field(default=None, ge=0, lt=1)
    reason: str = Field(min_length=1)
