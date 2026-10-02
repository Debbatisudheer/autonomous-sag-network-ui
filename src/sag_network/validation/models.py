from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ValidationStatus(str, Enum):
    """Outcome of one large-scale validation scenario."""

    PASS = "pass"
    FAIL = "fail"


class ValidationScenarioConfig(BaseModel):
    """Deterministic benchmark parameters for one scalable validation scenario."""

    scenario_id: str = Field(min_length=1)
    user_count: int = Field(ge=1)
    fault_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    interference_loss_db: float = Field(default=0.0, ge=0.0)
    traffic_multiplier: float = Field(default=1.0, gt=0.0)
    timestamp_s: float = Field(default=100.0, ge=0.0)
    telemetry_points: int = Field(default=4, ge=3)
    edge_source_limit: int = Field(default=10, ge=1)


class ValidationScenario(BaseModel):
    """Concrete deterministic benchmark state derived from one scenario config."""

    config: ValidationScenarioConfig
    user_ids: list[str]
    candidate_count: int = Field(ge=0)
    fault_user_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_users(self) -> ValidationScenario:
        expected_ids = [f"user-{index:04d}" for index in range(1, self.config.user_count + 1)]
        if self.user_ids != expected_ids:
            raise ValueError("user_ids must match the deterministic user-count sequence")
        if any(user_id not in set(self.user_ids) for user_id in self.fault_user_ids):
            raise ValueError("fault_user_ids must reference generated users")
        return self


class ValidationRunMetrics(BaseModel):
    """Measured and logical metrics emitted by one validation scenario run."""

    scenario_id: str = Field(min_length=1)
    status: ValidationStatus
    runtime_ms: float = Field(ge=0)
    user_count: int = Field(ge=1)
    candidate_count: int = Field(ge=0)
    telemetry_records: int = Field(ge=0)
    predictive_warnings: int = Field(ge=0)
    selected_decisions: int = Field(ge=0)
    selected_control_actions: int = Field(ge=0)
    detected_failures: int = Field(ge=0)
    recovered_failures: int = Field(ge=0)
    distributed_tasks: int = Field(ge=0)
    completed_distributed_tasks: int = Field(ge=0)
    placement_success_ratio: float = Field(ge=0, le=1)
    recovery_success_ratio: float = Field(ge=0, le=1)
    distributed_state_converged: bool
    message_delivered: int = Field(ge=0)
    deterministic_fingerprint: str = Field(min_length=64, max_length=64)


class ValidationAggregateReport(BaseModel):
    """Aggregate large-scale validation summary across a scenario matrix."""

    status: ValidationStatus
    scenarios: list[ValidationRunMetrics]
    total_users: int = Field(ge=0)
    total_telemetry_records: int = Field(ge=0)
    total_failures: int = Field(ge=0)
    total_recovered_failures: int = Field(ge=0)
    minimum_recovery_success_ratio: float = Field(ge=0, le=1)
    minimum_placement_success_ratio: float = Field(ge=0, le=1)
    all_distributed_state_converged: bool
    deterministic_matrix_fingerprint: str = Field(min_length=64, max_length=64)


__all__ = [
    "ValidationAggregateReport",
    "ValidationRunMetrics",
    "ValidationScenario",
    "ValidationScenarioConfig",
    "ValidationStatus",
]
