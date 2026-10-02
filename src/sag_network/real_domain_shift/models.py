from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DomainShiftEvidence(str, Enum):
    PUBLIC_DATA = "PUBLIC DATA"
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"


class DomainShiftConfig(BaseModel):
    lag_steps: int = Field(default=3, ge=2, le=10)
    calibration_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    minimum_samples: int = Field(default=20, ge=6)
    minimum_comparison_samples: int = Field(default=20, ge=1)
    max_rows_per_series: int = Field(default=50000, ge=100)
    psi_threshold: float = Field(default=0.25, gt=0)
    cdf_distance_threshold: float = Field(default=0.10, gt=0, le=1)
    standardized_mean_threshold: float = Field(default=0.50, gt=0)
    std_ratio_threshold: float = Field(default=1.50, gt=1)
    histogram_bins: int = Field(default=10, ge=4, le=50)


class DomainShiftSeries(BaseModel):
    source_id: str = Field(min_length=1)
    reference_samples: int = Field(ge=1)
    comparison_samples: int = Field(ge=1)
    reference_mean: float
    comparison_mean: float
    reference_std: float = Field(ge=0)
    comparison_std: float = Field(ge=0)
    standardized_mean_shift: float = Field(ge=0)
    std_ratio: float = Field(ge=1)
    population_stability_index: float = Field(ge=0)
    empirical_cdf_distance: float = Field(ge=0, le=1)
    shift_score: float = Field(ge=0, le=1)
    shift_detected: bool
    detection_reasons: tuple[str, ...]
    series_fingerprint: str = Field(min_length=64, max_length=64)


class DomainShiftReport(BaseModel):
    name: str = "Real-World Domain Shift Detection"
    phase: str = "65"
    status: str
    evidence_class: DomainShiftEvidence
    dataset_path: str
    source_sha256: str
    provenance_verified: bool
    row_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    analyzed_series_count: int = Field(ge=0)
    shifted_series_count: int = Field(ge=0)
    reference_window: str = "chronological_fit_partition"
    comparison_window: str = "chronological_final_test_partition"
    aggregate_reference_samples: int = Field(ge=1)
    aggregate_comparison_samples: int = Field(ge=1)
    aggregate_mean_shift_score: float = Field(ge=0, le=1)
    aggregate_max_shift_score: float = Field(ge=0, le=1)
    shift_rate: float = Field(ge=0, le=1)
    series_results: tuple[DomainShiftSeries, ...]
    detection_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool = False
