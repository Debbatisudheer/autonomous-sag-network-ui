from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric


class ForecastMethod(str, Enum):
    """Deterministic forecasting methods supported by the baseline predictor."""

    LAST_VALUE = "last_value"
    LINEAR_TREND = "linear_trend"


class PredictionStatus(str, Enum):
    """Outcome state for one source/metric prediction request."""

    READY = "ready"
    INSUFFICIENT_HISTORY = "insufficient_history"
    STALE_INPUT = "stale_input"


class WarningSeverity(str, Enum):
    """Severity of a predicted threshold violation."""

    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


class PredictiveConfig(BaseModel):
    """Deterministic boundaries for feature extraction and baseline forecasting."""

    history_window: int = Field(default=20, ge=2)
    min_points: int = Field(default=3, ge=2)
    horizon_steps: int = Field(default=3, ge=1)
    step_s: float = Field(default=1.0, gt=0)
    max_input_age_s: float = Field(default=5.0, ge=0)
    reject_stale_inputs: bool = True
    method: ForecastMethod = ForecastMethod.LINEAR_TREND
    minimum_confidence: float = Field(default=0.5, ge=0, le=1)


class TelemetryFeatureVector(BaseModel):
    """Deterministic statistical features extracted from one telemetry series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    sample_count: int = Field(ge=1)
    latest_value: float
    latest_timestamp_s: float = Field(ge=0)
    age_s: float = Field(ge=0)
    stale: bool
    mean_value: float
    standard_deviation: float = Field(ge=0)
    minimum_value: float
    maximum_value: float
    trend_per_s: float
    last_delta_per_s: float
    trend_r_squared: float = Field(ge=0, le=1)


class ForecastPoint(BaseModel):
    """One deterministic future estimate for one source/metric series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    forecast_timestamp_s: float = Field(ge=0)
    horizon_s: float = Field(ge=0)
    predicted_value: float
    confidence_score: float = Field(ge=0, le=1)
    method: ForecastMethod
    input_sample_count: int = Field(ge=1)
    source_timestamp_s: float = Field(ge=0)


class ForecastSeries(BaseModel):
    """Forecast trajectory plus the feature vector used to produce it."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    status: PredictionStatus
    method: ForecastMethod
    feature_vector: TelemetryFeatureVector | None = None
    points: list[ForecastPoint] = Field(default_factory=list)
    reason: str | None = None


class PredictiveThresholdRule(BaseModel):
    """Scenario-specific threshold policy used only for predictive early warnings."""

    source_id: str | None = Field(default=None, min_length=1)
    metric: TelemetryMetric
    minimum_value: float | None = None
    maximum_value: float | None = None
    warning_within_s: float = Field(default=10.0, gt=0)
    critical_within_s: float = Field(default=3.0, gt=0)
    minimum_confidence: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> PredictiveThresholdRule:
        if self.minimum_value is None and self.maximum_value is None:
            raise ValueError("at least one threshold bound is required")
        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value > self.maximum_value
        ):
            raise ValueError("minimum_value must not exceed maximum_value")
        if self.critical_within_s > self.warning_within_s:
            raise ValueError("critical_within_s must not exceed warning_within_s")
        return self


class PredictiveEarlyWarning(BaseModel):
    """Predicted threshold violation requiring downstream attention."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    severity: WarningSeverity
    forecast_timestamp_s: float = Field(ge=0)
    lead_time_s: float = Field(ge=0)
    predicted_value: float
    threshold_value: float
    threshold_direction: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class PredictiveReport(BaseModel):
    """Deterministic predictive-intelligence output for one simulation instant."""

    timestamp_s: float = Field(ge=0)
    features: list[TelemetryFeatureVector] = Field(default_factory=list)
    forecasts: list[ForecastSeries] = Field(default_factory=list)
    early_warnings: list[PredictiveEarlyWarning] = Field(default_factory=list)

    @property
    def warning_count(self) -> int:
        return len(self.early_warnings)
