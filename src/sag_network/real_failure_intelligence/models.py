from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RealFailureEvidence(str, Enum):
    PUBLIC_DATA = "PUBLIC DATA"
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"


class RealFailureIntelligenceConfig(BaseModel):
    lag_steps: int = Field(default=3, ge=2, le=10)
    calibration_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    ridge_alpha: float = Field(default=1e-6, gt=0)
    confidence_level: float = Field(default=0.90, gt=0.5, lt=1.0)
    minimum_calibration_samples: int = Field(default=20, ge=1)
    minimum_samples: int = Field(default=20, ge=6)
    max_rows_per_series: int = Field(default=50000, ge=100)
    normal_lower_quantile: float = Field(default=0.01, ge=0, lt=0.5)
    normal_upper_quantile: float = Field(default=0.99, gt=0.5, le=1)


class RealFailureSeries(BaseModel):
    source_id: str = Field(min_length=1)
    sample_count: int = Field(ge=1)
    fit_samples: int = Field(ge=1)
    calibration_samples: int = Field(ge=1)
    test_samples: int = Field(ge=1)
    conformal_quantile: float = Field(ge=0)
    normal_lower_bound: float
    normal_upper_bound: float
    observed_anomaly_count: int = Field(ge=0)
    flagged_risk_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1_score: float = Field(ge=0, le=1)
    mean_risk_score: float = Field(ge=0, le=1)
    max_risk_score: float = Field(ge=0, le=1)
    series_fingerprint: str = Field(min_length=64, max_length=64)


class RealFailureIntelligenceReport(BaseModel):
    name: str = "Real Failure Intelligence"
    phase: str = "64"
    status: str
    evidence_class: RealFailureEvidence
    dataset_path: str
    source_sha256: str
    provenance_verified: bool
    row_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    analyzed_series_count: int = Field(ge=0)
    confidence_level: float = Field(gt=0.5, lt=1.0)
    observed_anomaly_count: int = Field(ge=0)
    flagged_risk_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1_score: float = Field(ge=0, le=1)
    mean_risk_score: float = Field(ge=0, le=1)
    max_risk_score: float = Field(ge=0, le=1)
    series_results: tuple[RealFailureSeries, ...]
    intelligence_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool = False
