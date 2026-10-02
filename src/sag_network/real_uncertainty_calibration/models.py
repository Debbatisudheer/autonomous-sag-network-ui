from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RealUncertaintyEvidence(str, Enum):
    PUBLIC_DATA = "PUBLIC DATA"
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"


class RealUncertaintyCalibrationConfig(BaseModel):
    lag_steps: int = Field(default=3, ge=2, le=10)
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    calibration_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    ridge_alpha: float = Field(default=1e-6, gt=0)
    confidence_level: float = Field(default=0.90, gt=0.5, lt=1.0)
    minimum_calibration_samples: int = Field(default=20, ge=1)
    max_rows_per_series: int = Field(default=50000, ge=100)
    minimum_samples: int = Field(default=20, ge=6)


class RealUncertaintySeries(BaseModel):
    source_id: str = Field(min_length=1)
    sample_count: int = Field(ge=1)
    fit_samples: int = Field(ge=1)
    calibration_samples: int = Field(ge=1)
    test_samples: int = Field(ge=1)
    confidence_level: float = Field(gt=0.5, lt=1.0)
    calibration_quantile: float = Field(ge=0)
    empirical_coverage: float = Field(ge=0, le=1)
    coverage_gap: float
    coverage_status: str
    mean_interval_width: float = Field(ge=0)
    calibration_residual_mae: float = Field(ge=0)
    interval_model_fingerprint: str = Field(min_length=64, max_length=64)


class RealUncertaintyCalibrationReport(BaseModel):
    name: str = "Real-World Uncertainty Calibration"
    phase: str = "63"
    status: str
    evidence_class: RealUncertaintyEvidence
    dataset_path: str
    source_sha256: str
    provenance_verified: bool
    row_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    calibrated_series_count: int = Field(ge=0)
    confidence_level: float = Field(gt=0.5, lt=1.0)
    calibration_method: str = "split_conformal_absolute_residual"
    aggregate_test_sample_count: int = Field(ge=1)
    aggregate_empirical_coverage: float = Field(ge=0, le=1)
    aggregate_coverage_gap: float
    aggregate_mean_interval_width: float = Field(ge=0)
    aggregate_calibration_residual_mae: float = Field(ge=0)
    series_results: tuple[RealUncertaintySeries, ...]
    calibration_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool = False
