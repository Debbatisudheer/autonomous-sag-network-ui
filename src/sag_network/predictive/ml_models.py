from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric


class MLBaselineStatus(str, Enum):
    """Training outcome for one source/metric ML baseline."""

    TRAINED = "trained"
    INSUFFICIENT_HISTORY = "insufficient_history"


class MLBaselineConfig(BaseModel):
    """Deterministic configuration for the Phase 32 supervised baseline."""

    lag_steps: int = Field(default=3, ge=2, le=10)
    minimum_samples: int = Field(default=12, ge=4)
    test_fraction: float = Field(default=0.25, gt=0, lt=0.5)
    ridge_alpha: float = Field(default=1e-6, gt=0)
    horizon_steps: int = Field(default=3, ge=1, le=20)
    step_s: float = Field(default=1.0, gt=0)


class MLBaselineMetrics(BaseModel):
    """Deterministic validation metrics for one trained baseline."""

    train_samples: int = Field(ge=1)
    test_samples: int = Field(ge=1)
    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    r_squared: float


class MLBaselineModel(BaseModel):
    """Immutable learned coefficients and provenance for one telemetry series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    lag_steps: int = Field(ge=2)
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    ridge_alpha: float = Field(gt=0)
    training_samples: int = Field(ge=1)
    metrics: MLBaselineMetrics
    model_fingerprint: str = Field(min_length=64, max_length=64)


class MLBaselineForecast(BaseModel):
    """Recursive multi-step forecast emitted by the trained baseline."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    status: MLBaselineStatus
    forecast_timestamp_s: float = Field(ge=0)
    horizon_s: float = Field(ge=0)
    predicted_value: float | None = None
    confidence_score: float = Field(ge=0, le=1)
    model_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    reason: str | None = None


class MLBaselineSeries(BaseModel):
    """Training artifact and future forecast for one source/metric series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    status: MLBaselineStatus
    model: MLBaselineModel | None = None
    forecasts: list[MLBaselineForecast] = Field(default_factory=list)
    reason: str | None = None


class MLBaselineReport(BaseModel):
    """Deterministic Phase 32 training and inference report."""

    timestamp_s: float = Field(ge=0)
    config: MLBaselineConfig
    series: list[MLBaselineSeries] = Field(default_factory=list)

    @property
    def trained_count(self) -> int:
        return sum(item.status is MLBaselineStatus.TRAINED for item in self.series)
