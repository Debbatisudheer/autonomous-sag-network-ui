from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric


class DeepLearningStatus(str, Enum):
    """Training outcome for one time-series neural model."""

    TRAINED = "trained"
    INSUFFICIENT_HISTORY = "insufficient_history"


class DeepLearningConfig(BaseModel):
    """Deterministic configuration for the Phase 33 time-series neural baseline."""

    lag_steps: int = Field(default=6, ge=2, le=32)
    minimum_samples: int = Field(default=24, ge=8)
    test_fraction: float = Field(default=0.25, gt=0, lt=0.5)
    hidden_units: int = Field(default=8, ge=2, le=64)
    epochs: int = Field(default=300, ge=1, le=5000)
    learning_rate: float = Field(default=0.02, gt=0, le=1)
    horizon_steps: int = Field(default=3, ge=1, le=32)
    step_s: float = Field(default=1.0, gt=0)
    seed: int = Field(default=17, ge=0, le=2**31 - 1)


class DeepLearningMetrics(BaseModel):
    """Deterministic validation metrics for one neural time-series model."""

    train_samples: int = Field(ge=1)
    test_samples: int = Field(ge=1)
    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    r_squared: float
    train_loss: float = Field(ge=0)


class DeepLearningModel(BaseModel):
    """Immutable learned neural-network parameters and training provenance."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    lag_steps: int = Field(ge=2)
    hidden_units: int = Field(ge=2)
    input_mean: tuple[float, ...]
    input_scale: tuple[float, ...]
    target_mean: float
    target_scale: float = Field(gt=0)
    hidden_weights: tuple[tuple[float, ...], ...]
    hidden_bias: tuple[float, ...]
    output_weights: tuple[float, ...]
    output_bias: float
    training_samples: int = Field(ge=1)
    epochs: int = Field(ge=1)
    learning_rate: float = Field(gt=0)
    metrics: DeepLearningMetrics
    model_fingerprint: str = Field(min_length=64, max_length=64)


class DeepLearningForecast(BaseModel):
    """Recursive multi-step forecast emitted by a trained neural model."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    status: DeepLearningStatus
    forecast_timestamp_s: float = Field(ge=0)
    horizon_s: float = Field(ge=0)
    predicted_value: float | None = None
    confidence_score: float = Field(ge=0, le=1)
    model_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    reason: str | None = None


class DeepLearningSeries(BaseModel):
    """Training artifact and future forecast for one telemetry series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    status: DeepLearningStatus
    model: DeepLearningModel | None = None
    forecasts: list[DeepLearningForecast] = Field(default_factory=list)
    reason: str | None = None


class DeepLearningReport(BaseModel):
    """Deterministic Phase 33 training and inference report."""

    timestamp_s: float = Field(ge=0)
    config: DeepLearningConfig
    series: list[DeepLearningSeries] = Field(default_factory=list)

    @property
    def trained_count(self) -> int:
        return sum(item.status is DeepLearningStatus.TRAINED for item in self.series)
