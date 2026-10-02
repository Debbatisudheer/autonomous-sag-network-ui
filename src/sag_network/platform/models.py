from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.topology import NetworkTopology
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.edge.models import EdgeFabricSnapshot
from sag_network.interference.model import InterferenceEvaluation
from sag_network.telemetry.models import TelemetryRecord


class PlatformStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class PlatformStage(str, Enum):
    OBSERVE = "observe"
    DIGITAL_TWIN_SYNC = "digital_twin_sync"
    PREDICT = "predict"
    DECIDE = "decide"
    OPTIMIZE = "optimize"
    RECOVER = "recover"
    DISTRIBUTE = "distribute"
    FEEDBACK = "feedback"


class PlatformStageResult(BaseModel):
    stage: PlatformStage
    status: PlatformStatus
    timestamp_s: float = Field(ge=0)
    detail: str = Field(min_length=1)


class AutonomousPlatformConfig(BaseModel):
    """Final platform orchestration bounds and deterministic operating policy."""

    platform_id: str = Field(min_length=1)
    network_name: str = Field(default="autonomous-sag-network", min_length=1)
    telemetry_history_limit: int = Field(default=2000, ge=1)
    twin_history_limit: int = Field(default=100, ge=1)
    maximum_decisions: int = Field(default=1000, ge=1)
    maximum_control_actions: int = Field(default=1000, ge=1)
    maximum_recovery_actions: int = Field(default=100, ge=1)
    maximum_distributed_tasks: int = Field(default=1000, ge=1)
    require_distributed_convergence: bool = True


class PlatformCycleInput(BaseModel):
    """All validated state inputs required for one autonomous platform cycle."""

    timestamp_s: float = Field(ge=0)
    network_snapshot: UnifiedNetworkSnapshot
    telemetry_records: list[TelemetryRecord]
    edge_fabric: EdgeFabricSnapshot
    topology: NetworkTopology | None = None
    scheduling_snapshot: SpectrumSchedulingSnapshot | None = None
    interference_evaluations: list[InterferenceEvaluation] = Field(default_factory=list)
    failure_network_snapshot: UnifiedNetworkSnapshot | None = None
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timestamps(self) -> PlatformCycleInput:
        if self.network_snapshot.timestamp_s != self.timestamp_s:
            raise ValueError("network_snapshot timestamp must match platform cycle timestamp")
        if self.edge_fabric.timestamp_s != self.timestamp_s:
            raise ValueError("edge_fabric timestamp must match platform cycle timestamp")
        if (
            self.scheduling_snapshot is not None
            and self.scheduling_snapshot.timestamp_s != self.timestamp_s
        ):
            raise ValueError("scheduling_snapshot timestamp must match platform cycle timestamp")
        if (
            self.failure_network_snapshot is not None
            and self.failure_network_snapshot.timestamp_s != self.timestamp_s
        ):
            raise ValueError(
                "failure_network_snapshot timestamp must match platform cycle timestamp"
            )
        if any(
            record.timestamp_s > self.timestamp_s for record in self.telemetry_records
        ):
            raise ValueError("telemetry records must not be later than platform cycle timestamp")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids must be unique")
        return self


class PlatformCycleReport(BaseModel):
    """Complete end-to-end outcome for one autonomous SAG operating cycle."""

    platform_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    status: PlatformStatus
    stages: list[PlatformStageResult]
    twin_snapshot_id: str = Field(min_length=1)
    telemetry_record_count: int = Field(ge=0)
    telemetry_state_sample_count: int = Field(ge=0)
    telemetry_stale_sample_count: int = Field(ge=0)
    predictive_warning_count: int = Field(ge=0)
    decision_count: int = Field(ge=0)
    control_action_count: int = Field(ge=0)
    verified_control_action_count: int = Field(ge=0)
    detected_failure_count: int = Field(ge=0)
    recovered_failure_count: int = Field(ge=0)
    distributed_task_count: int = Field(ge=0)
    completed_distributed_task_count: int = Field(ge=0)
    distributed_state_converged: bool
    message_delivered: int = Field(ge=0)
    feedback_events: list[str] = Field(default_factory=list)
    deterministic_fingerprint: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_stage_set(self) -> PlatformCycleReport:
        expected = list(PlatformStage)
        actual = [stage.stage for stage in self.stages]
        if actual != expected:
            raise ValueError("platform stages must appear exactly once in canonical order")
        if self.verified_control_action_count > self.control_action_count:
            raise ValueError("verified control actions cannot exceed total control actions")
        if self.recovered_failure_count > self.detected_failure_count:
            raise ValueError("recovered failures cannot exceed detected failures")
        return self


__all__ = [
    "AutonomousPlatformConfig",
    "PlatformCycleInput",
    "PlatformCycleReport",
    "PlatformStage",
    "PlatformStageResult",
    "PlatformStatus",
]
