from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class BaselineMethod(str, Enum):
    """Deterministic forecasting methods compared in Phase 50."""

    PERSISTENCE = "persistence"
    ROLLING_MEAN = "rolling_mean"
    ML_PREDICTIVE_BASELINE = "ml_predictive_baseline"


class BaselineComparisonConfig(BaseModel):
    """Configuration shared by all Phase 50 forecasting baselines."""

    lag_steps: int = Field(default=3, ge=2, le=10)
    minimum_training_samples: int = Field(default=12, ge=4)
    rolling_window: int = Field(default=3, ge=1, le=20)
    holdout_size: int = Field(default=6, ge=1, le=100)


class BaselineMetricResult(BaseModel):
    """Error metrics for one forecasting baseline."""

    method: BaselineMethod
    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    predictions: tuple[float, ...] = Field(min_length=1)
    actuals: tuple[float, ...] = Field(min_length=1)


class BaselineComparison(BaseModel):
    """Comparison of one method against the persistence reference baseline."""

    reference_method: BaselineMethod
    comparison_method: BaselineMethod
    mae_delta: float
    rmse_delta: float
    relative_mae_delta: float | None
    relative_rmse_delta: float | None


class BaselineComparisonResult(BaseModel):
    """Complete deterministic Phase 50 baseline-comparison result."""

    experiment_id: str = Field(min_length=1, max_length=128)
    training_count: int = Field(ge=1)
    holdout_count: int = Field(ge=1)
    metric_results: tuple[BaselineMetricResult, ...] = Field(min_length=1)
    comparisons: tuple[BaselineComparison, ...]
    result_fingerprint: str = Field(min_length=64, max_length=64)
    fixture: str = Field(min_length=1)
