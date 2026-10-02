from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class BenchmarkDirection(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class BenchmarkMetric(BaseModel):
    metric_id: str = Field(min_length=1, max_length=128)
    baseline: float
    observed: float
    direction: BenchmarkDirection
    target: float | None = None

    @property
    def delta(self) -> float:
        return self.observed - self.baseline

    @property
    def target_met(self) -> bool:
        if self.target is None:
            return True
        if self.direction is BenchmarkDirection.HIGHER_IS_BETTER:
            return self.observed >= self.target
        return self.observed <= self.target


class BenchmarkScenario(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    metrics: tuple[BenchmarkMetric, ...] = Field(min_length=1)


class BenchmarkResult(BaseModel):
    benchmark_id: str = Field(min_length=1, max_length=128)
    scenario_count: int = Field(ge=1)
    metric_count: int = Field(ge=1)
    scenarios_passed: int = Field(ge=0)
    metric_targets_met: int = Field(ge=0)
    total_metrics: int = Field(ge=1)
    pass_rate: float = Field(ge=0.0, le=1.0)
    benchmark_fingerprint: str = Field(min_length=64, max_length=64)
    deterministic: bool
    network_mutation: bool
    fixture: str = Field(min_length=1)