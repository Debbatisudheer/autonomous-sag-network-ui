from __future__ import annotations

import hashlib
import json

from sag_network.decision.engine import DecisionEngine
from sag_network.decision.models import DecisionConfig, DecisionPriority
from sag_network.digital_twin.engine import DigitalTwin
from sag_network.digital_twin.models import DigitalTwinConfig, DigitalTwinSnapshot
from sag_network.edge.coordinator import DistributedArchitectureEngine
from sag_network.edge.messaging import InMemoryMessageBroker
from sag_network.edge.models import DistributedArchitectureConfig, DistributedCycleReport
from sag_network.edge.pipeline import build_pipeline_tasks
from sag_network.optimization.engine import AutonomousOptimizationEngine
from sag_network.optimization.models import ControlState, OptimizationConfig
from sag_network.platform.models import (
    AutonomousPlatformConfig,
    PlatformCycleInput,
    PlatformCycleReport,
    PlatformStage,
    PlatformStageResult,
    PlatformStatus,
)
from sag_network.predictive.engine import PredictiveIntelligenceEngine
from sag_network.predictive.models import PredictiveConfig, PredictiveThresholdRule
from sag_network.recovery.engine import FailureRecoveryEngine
from sag_network.recovery.models import RecoveryConfig, SelfHealingState
from sag_network.telemetry.models import (
    RealTimeStateSnapshot,
    TelemetryIngestionConfig,
    TelemetryMetric,
    TelemetryTwinLink,
)
from sag_network.telemetry.state import TelemetryStateStore


class AutonomousSAGPlatform:
    """Final deterministic orchestration layer for the complete SAG software testbed."""

    def __init__(self, config: AutonomousPlatformConfig) -> None:
        self.config = config
        self.telemetry = TelemetryStateStore(
            config=TelemetryIngestionConfig(history_limit=config.telemetry_history_limit)
        )
        self.twin = DigitalTwin(
            DigitalTwinConfig(
                twin_id=f"{config.platform_id}-twin",
                network_name=config.network_name,
                history_limit=config.twin_history_limit,
            )
        )
        self.predictive = PredictiveIntelligenceEngine(
            PredictiveConfig(horizon_steps=3, step_s=1.0, min_points=3, minimum_confidence=0.0)
        )
        self.decision = DecisionEngine(
            DecisionConfig(minimum_confidence=0.0, maximum_actions=config.maximum_decisions)
        )
        self.optimization = AutonomousOptimizationEngine(
            OptimizationConfig(
                maximum_actions=config.maximum_control_actions,
                minimum_expected_gain=0.0,
            )
        )
        self.recovery = FailureRecoveryEngine(
            RecoveryConfig(maximum_recovery_actions=config.maximum_recovery_actions)
        )
        self.distributed = DistributedArchitectureEngine(
            DistributedArchitectureConfig(maximum_tasks_per_cycle=config.maximum_distributed_tasks)
        )
        self.control_state: ControlState | None = None
        self.healing_state: SelfHealingState | None = None
        self._last_timestamp_s: float | None = None
        self._cycle_count = 0

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def latest_twin_snapshot(self) -> DigitalTwinSnapshot | None:
        return self.twin.latest

    @property
    def latest_control_state(self) -> ControlState | None:
        return self.control_state

    @property
    def latest_healing_state(self) -> SelfHealingState | None:
        return self.healing_state

    @staticmethod
    def _fingerprint(payload: object) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _validate_cycle_order(self, timestamp_s: float) -> None:
        if self._last_timestamp_s is not None and timestamp_s <= self._last_timestamp_s:
            raise ValueError("platform cycle timestamps must increase strictly")

    @staticmethod
    def _source_ids(cycle: PlatformCycleInput) -> list[str]:
        if cycle.source_ids:
            return sorted(cycle.source_ids)
        return sorted(
            f"{association.selected_resource_id}:{association.user_id}"
            for association in cycle.network_snapshot.associations
            if association.selected_resource_id is not None
        )

    def _sync_twin(self, cycle: PlatformCycleInput) -> DigitalTwinSnapshot:
        snapshot_id = f"snapshot-{self._cycle_count + 1:04d}"
        snapshot = DigitalTwin.create_snapshot(
            snapshot_id=snapshot_id,
            timestamp_s=cycle.timestamp_s,
            network_name=self.config.network_name,
            unified_state=cycle.network_snapshot,
            topology=cycle.topology,
            spectrum_state=cycle.scheduling_snapshot,
            interference_evaluations=cycle.interference_evaluations,
            source="autonomous-platform",
            metadata={"platform_id": self.config.platform_id, "cycle": str(self._cycle_count + 1)},
        )
        return self.twin.sync(snapshot)

    def _distributed_cycle(
        self, cycle: PlatformCycleInput, state_payload: dict[str, object]
    ) -> tuple[DistributedCycleReport, int]:
        source_ids = self._source_ids(cycle)
        tasks = [
            task
            for source_id in source_ids
            for task in build_pipeline_tasks(timestamp_s=cycle.timestamp_s, source_id=source_id)
        ]
        tasks = tasks[: self.config.maximum_distributed_tasks]
        message = InMemoryMessageBroker.create_message(
            source_node_id="platform-controller",
            destination_node_id="regional-controller",
            topic="platform.feedback",
            timestamp_s=cycle.timestamp_s,
            priority=DecisionPriority.HIGH,
            payload=state_payload,
            ttl_s=5.0,
        )
        broker = InMemoryMessageBroker()
        broker.publish(message)
        delivered = len(
            broker.consume("regional-controller", now_s=cycle.timestamp_s + 1.0)
        )
        distributed_report, _ = self.distributed.run_cycle(
            timestamp_s=cycle.timestamp_s,
            fabric=cycle.edge_fabric,
            tasks=tasks,
            state_payloads={"platform": state_payload},
            replica_node_ids=[
                node.node_id
                for node in cycle.edge_fabric.nodes
                if node.node_type.value in {"regional_controller", "central_controller"}
            ],
        )
        return distributed_report, delivered

    def run_cycle(self, cycle: PlatformCycleInput) -> PlatformCycleReport:
        """Run one complete Sense-to-Feedback autonomous operating cycle."""
        self._validate_cycle_order(cycle.timestamp_s)

        telemetry_result_counts = {"accepted": 0, "rejected": 0}
        ordered_records = sorted(
            cycle.telemetry_records,
            key=lambda item: (item.timestamp_s, item.sequence, item.record_id),
        )
        for record in ordered_records:
            result = self.telemetry.ingest(record, reference_time_s=cycle.timestamp_s)
            telemetry_result_counts["accepted"] += result.accepted_count
            telemetry_result_counts["rejected"] += result.rejected_count
        telemetry_state: RealTimeStateSnapshot = self.telemetry.snapshot(
            timestamp_s=cycle.timestamp_s
        )

        twin_snapshot = self._sync_twin(cycle)
        twin_link = TelemetryTwinLink(
            twin_snapshot_id=twin_snapshot.snapshot_id,
            twin_timestamp_s=twin_snapshot.timestamp_s,
            telemetry_timestamp_s=telemetry_state.timestamp_s,
            sample_count=telemetry_state.sample_count,
            stale_sample_count=telemetry_state.stale_sample_count,
        )

        rules = [
            PredictiveThresholdRule(
                metric=TelemetryMetric.SINR_DB,
                minimum_value=10.0,
                warning_within_s=5.0,
                critical_within_s=3.0,
                minimum_confidence=0.0,
            )
        ]
        predictive_report = self.predictive.analyze(
            cycle.telemetry_records,
            reference_time_s=cycle.timestamp_s,
            rules=rules,
        )
        decision_report = self.decision.decide(
            predictive_report,
            network_snapshot=cycle.network_snapshot,
            scheduling_snapshot=cycle.scheduling_snapshot,
        )
        optimization_report = self.optimization.run(
            decision_report,
            network_snapshot=cycle.network_snapshot,
            scheduling_snapshot=cycle.scheduling_snapshot,
            state=self.control_state,
        )
        self.control_state = optimization_report.execution.resulting_state

        recovery_network = cycle.failure_network_snapshot or cycle.network_snapshot
        recovery_report = self.recovery.run(
            telemetry_state=telemetry_state,
            network_snapshot=recovery_network,
            scheduling_snapshot=cycle.scheduling_snapshot,
            optimization_report=optimization_report,
            twin_snapshot=twin_snapshot,
            control_state=self.control_state,
            healing_state=self.healing_state,
        )
        self.healing_state = recovery_report.self_healing_state
        self.control_state = recovery_report.resulting_control_state or self.control_state

        state_payload = {
            "platform_id": self.config.platform_id,
            "cycle_timestamp_s": cycle.timestamp_s,
            "twin_snapshot_id": twin_snapshot.snapshot_id,
            "telemetry_samples": telemetry_state.sample_count,
            "predictive_warnings": len(predictive_report.early_warnings),
            "selected_decisions": len(decision_report.selected_decisions),
            "selected_controls": len(optimization_report.plan.selected_actions),
            "detected_failures": len(recovery_report.detected_failures),
            "recovered_failures": sum(
                result.verified for result in recovery_report.execution_results
            ),
            "telemetry_twin_link": twin_link.model_dump(mode="json"),
        }
        distributed_report, message_delivered = self._distributed_cycle(cycle, state_payload)

        verified_controls = sum(result.verified for result in optimization_report.execution.results)
        completed_tasks = sum(result.completed for result in distributed_report.results)
        recovered_failures = sum(result.verified for result in recovery_report.execution_results)
        distributed_converged = self.distributed.state_store.is_converged("platform")
        stages = [
            PlatformStageResult(
                stage=PlatformStage.OBSERVE,
                status=PlatformStatus.PASS,
                timestamp_s=cycle.timestamp_s,
                detail="telemetry ingested and real-time state materialized",
            ),
            PlatformStageResult(
                stage=PlatformStage.DIGITAL_TWIN_SYNC,
                status=PlatformStatus.PASS,
                timestamp_s=cycle.timestamp_s,
                detail=f"digital twin synchronized at {twin_snapshot.snapshot_id}",
            ),
            PlatformStageResult(
                stage=PlatformStage.PREDICT,
                status=PlatformStatus.PASS,
                timestamp_s=cycle.timestamp_s,
                detail=f"generated {len(predictive_report.early_warnings)} predictive warnings",
            ),
            PlatformStageResult(
                stage=PlatformStage.DECIDE,
                status=PlatformStatus.PASS,
                timestamp_s=cycle.timestamp_s,
                detail=f"selected {len(decision_report.selected_decisions)} decisions",
            ),
            PlatformStageResult(
                stage=PlatformStage.OPTIMIZE,
                status=PlatformStatus.PASS,
                timestamp_s=cycle.timestamp_s,
                detail=(
                    f"selected {len(optimization_report.plan.selected_actions)} control actions; "
                    f"{verified_controls} verified"
                ),
            ),
            PlatformStageResult(
                stage=PlatformStage.RECOVER,
                status=(
                    PlatformStatus.PASS
                    if recovery_report.all_recovered
                    else PlatformStatus.FAIL
                ),
                timestamp_s=cycle.timestamp_s,
                detail=(
                    f"recovered {recovered_failures}/{len(recovery_report.detected_failures)} "
                    "detected failures"
                ),
            ),
            PlatformStageResult(
                stage=PlatformStage.DISTRIBUTE,
                status=(
                    PlatformStatus.PASS
                    if (
                        not distributed_report.rejected_task_ids
                        and (
                            distributed_converged
                            or not self.config.require_distributed_convergence
                        )
                    )
                    else PlatformStatus.FAIL
                ),
                timestamp_s=cycle.timestamp_s,
                detail=(
                    f"completed {completed_tasks}/{len(distributed_report.results)} "
                    "distributed tasks"
                ),
            ),
            PlatformStageResult(
                stage=PlatformStage.FEEDBACK,
                status=PlatformStatus.PASS,
                timestamp_s=cycle.timestamp_s,
                detail="control/recovery verification fed back into platform state",
            ),
        ]
        status = (
            PlatformStatus.PASS
            if all(stage.status is PlatformStatus.PASS for stage in stages)
            and telemetry_result_counts["rejected"] == 0
            else PlatformStatus.FAIL
        )
        feedback_events = [
            f"twin:{twin_snapshot.snapshot_id}",
            f"telemetry:{telemetry_state.sample_count}",
            f"controls_verified:{verified_controls}",
            f"recovered_failures:{recovered_failures}",
            f"distributed_converged:{distributed_converged}",
        ]
        fingerprint = self._fingerprint(
            {
                "platform_id": self.config.platform_id,
                "timestamp_s": cycle.timestamp_s,
                "twin_snapshot": twin_snapshot.model_dump(mode="json"),
                "predictive": predictive_report.model_dump(mode="json"),
                "decision": decision_report.model_dump(mode="json"),
                "optimization": optimization_report.model_dump(mode="json"),
                "recovery": recovery_report.model_dump(mode="json"),
                "distributed": distributed_report.model_dump(mode="json"),
                "message_delivered": message_delivered,
            }
        )
        self._last_timestamp_s = cycle.timestamp_s
        self._cycle_count += 1
        return PlatformCycleReport(
            platform_id=self.config.platform_id,
            timestamp_s=cycle.timestamp_s,
            status=status,
            stages=stages,
            twin_snapshot_id=twin_snapshot.snapshot_id,
            telemetry_record_count=len(cycle.telemetry_records),
            telemetry_state_sample_count=telemetry_state.sample_count,
            telemetry_stale_sample_count=telemetry_state.stale_sample_count,
            predictive_warning_count=len(predictive_report.early_warnings),
            decision_count=len(decision_report.selected_decisions),
            control_action_count=len(optimization_report.plan.selected_actions),
            verified_control_action_count=verified_controls,
            detected_failure_count=len(recovery_report.detected_failures),
            recovered_failure_count=recovered_failures,
            distributed_task_count=len(distributed_report.results),
            completed_distributed_task_count=completed_tasks,
            distributed_state_converged=distributed_converged,
            message_delivered=message_delivered,
            feedback_events=feedback_events,
            deterministic_fingerprint=fingerprint,
        )


__all__ = ["AutonomousSAGPlatform"]
