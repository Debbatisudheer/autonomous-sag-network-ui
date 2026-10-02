from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FailureMode(str, Enum):
    """Controlled failure modes exercised by Phase 51."""

    PACKET_LOSS = "packet_loss"
    LATENCY_SPIKE = "latency_spike"
    NODE_OUTAGE = "node_outage"
    RESOURCE_OVERLOAD = "resource_overload"


class FailureSeverity(str, Enum):
    """Deterministic severity classification for an injected failure."""

    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"


class StressScenario(BaseModel):
    """One deterministic stress/failure scenario."""

    scenario_id: str = Field(min_length=1, max_length=128)
    failure_mode: FailureMode
    baseline_value: float = Field(ge=0)
    stressed_value: float = Field(ge=0)
    recovered_value: float = Field(ge=0)
    recovery_tolerance: float = Field(default=0.01, ge=0)
    warning_threshold: float = Field(ge=0)
    critical_threshold: float = Field(ge=0)
    higher_is_worse: bool
    expected_severity: FailureSeverity


class StressFinding(BaseModel):
    """Observed effect of one injected failure."""

    scenario_id: str
    failure_mode: FailureMode
    baseline_value: float
    stressed_value: float
    absolute_delta: float
    relative_delta: float | None
    recovery_error: float
    severity: FailureSeverity
    threshold_breached: bool
    recovery_observed: bool


class StressCampaignResult(BaseModel):
    """Complete deterministic Phase 51 campaign result."""

    campaign_id: str = Field(min_length=1, max_length=128)
    scenario_count: int = Field(ge=1)
    finding_count: int = Field(ge=1)
    critical_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    findings: tuple[StressFinding, ...] = Field(min_length=1)
    campaign_fingerprint: str = Field(min_length=64, max_length=64)
    fixture: str = Field(min_length=1)
