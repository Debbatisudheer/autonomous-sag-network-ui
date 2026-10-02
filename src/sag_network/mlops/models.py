from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class MLOpsStage(str, Enum):
    """Lifecycle stage assigned to a registered model artifact."""

    REGISTERED = "registered"
    VALIDATED = "validated"
    PRODUCTION = "production"
    REJECTED = "rejected"


class DatasetLineage(BaseModel):
    """Immutable dataset provenance attached to a model artifact."""

    dataset_id: str = Field(min_length=1)
    dataset_fingerprint: str = Field(min_length=64, max_length=64)
    source: str = Field(min_length=1)
    record_count: int = Field(ge=1)
    fixture: str = Field(min_length=1)


class ModelEvaluation(BaseModel):
    """Validation metrics used by a deterministic model promotion gate."""

    mean_absolute_error: float = Field(ge=0)
    root_mean_squared_error: float = Field(ge=0)
    r_squared: float
    training_samples: int = Field(ge=1)
    test_samples: int = Field(ge=1)


class ModelArtifact(BaseModel):
    """Versioned model metadata with complete reproducibility lineage."""

    model_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    model_type: str = Field(min_length=1)
    model_fingerprint: str = Field(min_length=64, max_length=64)
    dataset_lineage: DatasetLineage
    feature_schema_fingerprint: str = Field(min_length=64, max_length=64)
    training_config_fingerprint: str = Field(min_length=64, max_length=64)
    evaluation: ModelEvaluation
    stage: MLOpsStage = MLOpsStage.REGISTERED
    artifact_fingerprint: str = Field(min_length=64, max_length=64)


class PromotionGate(BaseModel):
    """Deterministic thresholds required before production promotion."""

    minimum_r_squared: float = Field(ge=-1, le=1)
    maximum_root_mean_squared_error: float = Field(ge=0)
    minimum_test_samples: int = Field(ge=1)


class PromotionDecision(BaseModel):
    """Auditable result of evaluating one model artifact against a gate."""

    model_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    eligible: bool
    previous_stage: MLOpsStage
    resulting_stage: MLOpsStage
    reasons: tuple[str, ...]
    decision_fingerprint: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_rejection_consistency(self) -> PromotionDecision:
        if not self.eligible and self.resulting_stage is MLOpsStage.PRODUCTION:
            raise ValueError("ineligible model cannot enter production")
        return self


class MLOpsReport(BaseModel):
    """Deterministic Phase 47 registry and promotion report."""

    timestamp_s: float = Field(ge=0)
    registered_models: int = Field(ge=0)
    validated_models: int = Field(ge=0)
    production_models: int = Field(ge=0)
    rejected_models: int = Field(ge=0)
    promoted_model_id: str | None = None
    promoted_version: str | None = None
    registry_fingerprint: str = Field(min_length=64, max_length=64)
    promotion_fingerprint: str = Field(min_length=64, max_length=64)
    fixture: str = Field(min_length=1)
