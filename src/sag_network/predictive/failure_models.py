from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric


class FailureRiskLevel(str, Enum):
    """Deterministic operational level for a predicted failure condition."""

    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


class FailureDirection(str, Enum):
    """Direction in which a forecasted threshold is violated."""

    BELOW_MINIMUM = "below_minimum"
    ABOVE_MAXIMUM = "above_maximum"


class FailureThresholdRule(BaseModel):
    """Explicit scenario threshold used to classify predicted degradation."""

    source_id: str | None = Field(default=None, min_length=1)
    metric: TelemetryMetric
    minimum_value: float | None = None
    maximum_value: float | None = None
    warning_within_s: float = Field(default=10.0, gt=0)
    critical_within_s: float = Field(default=3.0, gt=0)
    uncertainty_buffer_multiplier: float = Field(default=1.0, ge=0)


class PredictedFailure(BaseModel):
    """One forecast-derived failure-risk condition; it does not mutate network state."""

    event_id: str = Field(min_length=64, max_length=64)
    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    direction: FailureDirection
    risk_level: FailureRiskLevel
    forecast_timestamp_s: float = Field(ge=0)
    lead_time_s: float = Field(ge=0)
    predicted_value: float
    threshold_value: float
    lower_bound: float
    upper_bound: float
    risk_score: float = Field(ge=0, le=1)
    uncertainty_score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class FailureIntelligenceSeries(BaseModel):
    """Failure-risk findings associated with one telemetry series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    predicted_failures: list[PredictedFailure] = Field(default_factory=list)


class FailureIntelligenceReport(BaseModel):
    """Deterministic predictive failure-intelligence output."""

    timestamp_s: float = Field(ge=0)
    rules: list[FailureThresholdRule] = Field(default_factory=list)
    series: list[FailureIntelligenceSeries] = Field(default_factory=list)

    @property
    def predicted_failure_count(self) -> int:
        return sum(len(item.predicted_failures) for item in self.series)
