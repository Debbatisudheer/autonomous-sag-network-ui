from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResearchStage(str, Enum):
    """Deterministic stages of the integrated SAG research platform."""

    EXPERIMENT = "experiment"
    STRESS = "stress"
    REPRODUCIBILITY = "reproducibility"


class ResearchComponent(BaseModel):
    """Registered subsystem exposed through the research platform."""

    component_id: str = Field(min_length=1, max_length=128)
    stage: ResearchStage
    capability: str = Field(min_length=1, max_length=256)
    enabled: bool = True


class ResearchRunResult(BaseModel):
    """Auditable result of one integrated research-platform run."""

    run_id: str = Field(min_length=1, max_length=128)
    component_count: int = Field(ge=1)
    stages_completed: tuple[ResearchStage, ...] = Field(min_length=1)
    experiment_fingerprint: str = Field(min_length=64, max_length=64)
    stress_fingerprint: str = Field(min_length=64, max_length=64)
    platform_fingerprint: str = Field(min_length=64, max_length=64)
    network_mutation: bool
    fixture: str = Field(min_length=1)
