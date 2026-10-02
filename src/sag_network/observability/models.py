from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MetricType(str, Enum):
    """Supported deterministic observability metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricSample(BaseModel):
    """One timestamped metric observation with bounded dimensions."""

    name: str = Field(min_length=1, max_length=128)
    metric_type: MetricType
    value: float
    timestamp_s: float = Field(ge=0)
    labels: dict[str, str] = Field(default_factory=dict)
    correlation_id: str = Field(min_length=1, max_length=128)


class TraceEvent(BaseModel):
    """One structured event associated with a distributed operation."""

    event_id: str = Field(min_length=1, max_length=128)
    timestamp_s: float = Field(ge=0)
    component: str = Field(min_length=1, max_length=128)
    event_name: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    attributes: dict[str, str] = Field(default_factory=dict)


class HealthStatus(str, Enum):
    """Aggregated health state exposed by the observability layer."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health summary for one SAG component."""

    component: str = Field(min_length=1, max_length=128)
    status: HealthStatus
    checks_total: int = Field(ge=0)
    checks_failed: int = Field(ge=0)
    last_check_timestamp_s: float | None = Field(default=None, ge=0)


class ObservabilitySnapshot(BaseModel):
    """Deterministic point-in-time observability export."""

    timestamp_s: float = Field(ge=0)
    metrics: tuple[MetricSample, ...]
    events: tuple[TraceEvent, ...]
    health: tuple[ComponentHealth, ...]
    metric_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    healthy_components: int = Field(ge=0)
    degraded_components: int = Field(ge=0)
    unhealthy_components: int = Field(ge=0)
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    fixture: str = Field(min_length=1)
