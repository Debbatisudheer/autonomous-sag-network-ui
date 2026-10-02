from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TrainingEvidence(str, Enum):
    PUBLIC_DATA = "PUBLIC DATA"
    SYNTHETIC_FIXTURE = "SYNTHETIC FIXTURE"


class RealDataTrainingConfig(BaseModel):
    lag_steps: int = Field(default=3, ge=2, le=10)
    minimum_samples: int = Field(default=20, ge=6)
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    ridge_alpha: float = Field(default=1e-6, gt=0)
    max_rows_per_series: int = Field(default=50000, ge=100)


class RealDataTrainingResult(BaseModel):
    source_id: str = Field(min_length=1)
    sample_count: int = Field(ge=0)
    training_samples: int = Field(ge=0)
    test_samples: int = Field(ge=0)
    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    r_squared: float
    model_fingerprint: str = Field(min_length=64, max_length=64)


class RealDataTrainingReport(BaseModel):
    name: str = "Real-Data Model Training"
    phase: str = "61"
    status: str
    evidence_class: TrainingEvidence
    dataset_path: str
    source_sha256: str
    provenance_verified: bool
    row_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    trained_series_count: int = Field(ge=0)
    results: list[RealDataTrainingResult]
    training_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool = False
