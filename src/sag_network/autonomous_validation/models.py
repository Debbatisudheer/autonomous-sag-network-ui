from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from sag_network.cross_domain_sag.models import CrossDomainSAGEvidence


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ValidationCheck(BaseModel):
    """One auditable Phase 79 validation assertion."""

    check_id: str = Field(min_length=1, max_length=128)
    phase: str = Field(min_length=1, max_length=8)
    status: ValidationStatus
    observed: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64)


class ValidationPhaseEvidence(BaseModel):
    """Compact evidence summary for one validated predecessor phase."""

    phase: str = Field(min_length=1, max_length=8)
    name: str = Field(min_length=1)
    status: ValidationStatus
    evidence_class: CrossDomainSAGEvidence
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    source_sha256: str = ""
    provenance_verified: bool = False
    key_metrics: dict[str, float] = Field(default_factory=dict)
    network_mutation: bool = False
    hardware_measurement: bool = False


class AutonomousValidationConfig(BaseModel):
    """Bounded configuration for the Phase 79 repeatable validation campaign."""

    timestamps_s: list[float] = Field(
        default_factory=lambda: [
            0.0,
            15.0,
            60.0,
            120.0,
            300.0,
            600.0,
            900.0,
            1200.0,
            1500.0,
            1800.0,
            2100.0,
            2400.0,
            2700.0,
            3000.0,
        ],
        min_length=2,
    )
    user_demand_bps: dict[str, float] = Field(
        default_factory=lambda: {
            "sag-user-01": 10e6,
            "sag-user-02": 10e6,
            "sag-user-03": 10e6,
        }
    )
    use_real_ephemeris: bool = False
    use_udp_loopback: bool = False
    timeout_s: float = Field(default=1.0, gt=0, le=10.0)
    minimum_telemetry_health: float = Field(default=0.75, ge=0, le=1)
    handover_hysteresis_db: float = Field(default=2.0, ge=0)
    handover_time_to_trigger_s: float = Field(default=5.0, ge=0)

    @model_validator(mode="after")
    def validate_inputs(self) -> AutonomousValidationConfig:
        if any(timestamp < 0 for timestamp in self.timestamps_s):
            raise ValueError("timestamps_s must contain non-negative values")
        if any(
            right < left
            for left, right in zip(self.timestamps_s, self.timestamps_s[1:], strict=False)
        ):
            raise ValueError("timestamps_s must be non-decreasing")
        if any(value < 0 for value in self.user_demand_bps.values()):
            raise ValueError("user_demand_bps values must be non-negative")
        return self

    model_config = {"validate_assignment": True}


class AutonomousValidationSummary(BaseModel):
    """Aggregate quality and continuity metrics across Phases 76–78."""

    check_count: int = Field(ge=1)
    passed_check_count: int = Field(ge=0)
    failed_check_count: int = Field(ge=0)
    phase_count: int = Field(ge=3)
    phase_76_coverage_ratio: float = Field(ge=0, le=1)
    phase_77_demand_satisfaction_ratio: float = Field(ge=0, le=1)
    phase_77_verification_success_ratio: float = Field(ge=0, le=1)
    phase_78_recovery_ratio: float = Field(ge=0, le=1)
    phase_78_verification_success_ratio: float = Field(ge=0, le=1)
    deterministic_repeatability: bool
    evidence_boundary_clean: bool


class AutonomousValidationReport(BaseModel):
    """Auditable Phase 79 consolidation of cross-domain, autonomy, and resilience evidence."""

    phase: str = "79"
    status: ValidationStatus
    name: str = "Autonomous SAG Validation"
    evidence_class: CrossDomainSAGEvidence
    phase_evidence: tuple[ValidationPhaseEvidence, ...] = Field(min_length=3, max_length=3)
    checks: tuple[ValidationCheck, ...] = Field(min_length=1)
    summary: AutonomousValidationSummary
    integration_fingerprint: str = Field(min_length=64, max_length=64)
    source_sha256: str = ""
    provenance_verified: bool = False
    propagation_model: str = Field(min_length=1)
    ephemeris_source: str = Field(min_length=1)
    external_network_used: bool = False
    network_mutation: bool = False
    hardware_measurement: bool = False

    @model_validator(mode="after")
    def validate_summary(self) -> AutonomousValidationReport:
        if self.summary.check_count != len(self.checks):
            raise ValueError("summary check_count must match checks")
        if self.summary.passed_check_count + self.summary.failed_check_count != len(self.checks):
            raise ValueError("summary pass/fail counts must match checks")
        return self


__all__ = [
    "AutonomousValidationConfig",
    "AutonomousValidationReport",
    "AutonomousValidationSummary",
    "ValidationCheck",
    "ValidationPhaseEvidence",
    "ValidationStatus",
]
