from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RealBaselineMethod(str, Enum):
    PERSISTENCE = "persistence"
    ROLLING_MEAN = "rolling_mean"
    PHASE61_RIDGE = "phase61_ridge"


class RealBaselineComparisonConfig(BaseModel):
    lag_steps: int = Field(default=3, ge=2, le=10)
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    ridge_alpha: float = Field(default=1e-6, gt=0)
    rolling_window: int = Field(default=3, ge=1, le=20)
    max_rows_per_series: int = Field(default=50000, ge=100)
    minimum_samples: int = Field(default=20, ge=6)


class RealBaselineMetric(BaseModel):
    method: RealBaselineMethod
    sample_count: int = Field(ge=1)
    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    r_squared: float


class RealSeriesComparison(BaseModel):
    source_id: str = Field(min_length=1)
    sample_count: int = Field(ge=1)
    training_samples: int = Field(ge=1)
    test_samples: int = Field(ge=1)
    metrics: tuple[RealBaselineMetric, ...] = Field(min_length=1)
    phase61_model_fingerprint: str = Field(min_length=64, max_length=64)


class RealBaselineComparisonReport(BaseModel):
    name: str = "Real-Data Baseline Comparison"
    phase: str = "62"
    status: str
    evidence_class: str
    dataset_path: str
    source_sha256: str
    provenance_verified: bool
    row_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    compared_series_count: int = Field(ge=0)
    aggregate_metrics: tuple[RealBaselineMetric, ...] = Field(min_length=1)
    series_results: tuple[RealSeriesComparison, ...]
    comparison_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool = False
