from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OnlineAdaptationEvidence(str, Enum):
    PUBLIC_DATA = "PUBLIC DATA"
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"


class OnlineAdaptationConfig(BaseModel):
    lag_steps: int = Field(default=3, ge=2, le=10)
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    ridge_alpha: float = Field(default=1e-6, gt=0)
    max_rows_per_series: int = Field(default=50000, ge=100)
    minimum_samples: int = Field(default=20, ge=6)
    adaptation_window: int = Field(default=500, ge=20)
    minimum_adaptation_samples: int = Field(default=50, ge=10)
    update_interval: int = Field(default=50, ge=1)
    shift_window: int = Field(default=100, ge=20)
    shift_threshold: float = Field(default=0.5, ge=0, le=1)
    force_initial_adaptation: bool = True


class OnlineMetric(BaseModel):
    method: str
    sample_count: int = Field(ge=1)
    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    r_squared: float


class OnlineAdaptationSeries(BaseModel):
    source_id: str = Field(min_length=1)
    sample_count: int = Field(ge=1)
    initial_fit_samples: int = Field(ge=1)
    stream_samples: int = Field(ge=1)
    static_metrics: OnlineMetric
    adaptive_metrics: OnlineMetric
    scheduled_update_count: int = Field(ge=0)
    shift_triggered_update_count: int = Field(ge=0)
    total_update_count: int = Field(ge=0)
    adaptation_window: int = Field(ge=1)
    shift_threshold: float = Field(ge=0, le=1)
    adaptation_delta_mae: float
    series_fingerprint: str = Field(min_length=64, max_length=64)


class OnlineAdaptationReport(BaseModel):
    name: str = "Real-World Online Model Adaptation"
    phase: str = "66"
    status: str
    evidence_class: OnlineAdaptationEvidence
    dataset_path: str
    source_sha256: str
    provenance_verified: bool
    row_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    adapted_series_count: int = Field(ge=0)
    aggregate_stream_sample_count: int = Field(ge=1)
    aggregate_static_metrics: OnlineMetric
    aggregate_adaptive_metrics: OnlineMetric
    aggregate_adaptation_delta_mae: float
    total_scheduled_update_count: int = Field(ge=0)
    total_shift_triggered_update_count: int = Field(ge=0)
    total_update_count: int = Field(ge=0)
    series_results: tuple[OnlineAdaptationSeries, ...]
    adaptation_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool = False
