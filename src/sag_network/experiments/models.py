from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ExperimentMetricDirection(str, Enum):
    """Expected direction for a metric when comparing treatment to baseline."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class ExperimentFactor(BaseModel):
    """One controlled factor and its deterministic value."""

    name: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=256)


class ExperimentVariant(BaseModel):
    """One reproducible experiment variant."""

    variant_id: str = Field(min_length=1, max_length=128)
    factors: tuple[ExperimentFactor, ...] = Field(min_length=1)
    replicate_count: int = Field(ge=1, le=1000)


class ExperimentMetricSpec(BaseModel):
    """Metric definition used to compare experiment variants."""

    name: str = Field(min_length=1, max_length=128)
    direction: ExperimentMetricDirection


class ExperimentDefinition(BaseModel):
    """Complete deterministic controlled-experiment definition."""

    experiment_id: str = Field(min_length=1, max_length=128)
    hypothesis: str = Field(min_length=1, max_length=512)
    seed: int = Field(ge=0)
    variants: tuple[ExperimentVariant, ...] = Field(min_length=2)
    metrics: tuple[ExperimentMetricSpec, ...] = Field(min_length=1)
    fixture: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_variants(self) -> ExperimentDefinition:
        variant_ids = [variant.variant_id for variant in self.variants]
        if len(set(variant_ids)) != len(variant_ids):
            raise ValueError("variant identifiers must be unique")
        metric_names = [metric.name for metric in self.metrics]
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("metric names must be unique")
        if self.variants[0].replicate_count != self.variants[1].replicate_count:
            raise ValueError("all variants must use the same replicate count")
        return self


class ExperimentMetricResult(BaseModel):
    """Aggregated metric result for one experiment variant."""

    metric_name: str = Field(min_length=1, max_length=128)
    variant_id: str = Field(min_length=1, max_length=128)
    samples: tuple[float, ...] = Field(min_length=1)
    mean: float


class ExperimentComparison(BaseModel):
    """Baseline-to-treatment comparison for one metric."""

    metric_name: str = Field(min_length=1, max_length=128)
    baseline_variant_id: str = Field(min_length=1, max_length=128)
    treatment_variant_id: str = Field(min_length=1, max_length=128)
    baseline_mean: float
    treatment_mean: float
    absolute_delta: float
    relative_delta: float | None
    direction: ExperimentMetricDirection
    treatment_improved: bool


class ExperimentResult(BaseModel):
    """Complete deterministic result of one controlled experiment."""

    experiment_id: str = Field(min_length=1, max_length=128)
    seed: int = Field(ge=0)
    metric_results: tuple[ExperimentMetricResult, ...]
    comparisons: tuple[ExperimentComparison, ...]
    result_fingerprint: str = Field(min_length=64, max_length=64)
    fixture: str = Field(min_length=1)


class ExperimentReport(BaseModel):
    """Auditable summary produced by the Phase 49 experiment runner."""

    experiment_id: str = Field(min_length=1, max_length=128)
    variant_count: int = Field(ge=2)
    metric_count: int = Field(ge=1)
    replicate_count: int = Field(ge=1)
    comparison_count: int = Field(ge=1)
    result_fingerprint: str = Field(min_length=64, max_length=64)
    fixture: str = Field(min_length=1)
