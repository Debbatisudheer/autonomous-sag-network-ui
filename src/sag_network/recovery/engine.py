from __future__ import annotations

from sag_network.digital_twin.models import DigitalTwinSnapshot
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.optimization.models import ControlState, OptimizationReport
from sag_network.recovery.detector import FailureDetector
from sag_network.recovery.diagnosis import FailureDiagnoser
from sag_network.recovery.executor import SelfHealingExecutor
from sag_network.recovery.models import (
    FailureRecoveryReport,
    FailureStatus,
    RecoveryConfig,
    SelfHealingState,
)
from sag_network.recovery.planner import RecoveryPlanner
from sag_network.telemetry.models import RealTimeStateSnapshot


class FailureRecoveryEngine:
    """Closed-loop Phase 20 engine: detect, diagnose, plan, recover, and reconcile."""

    def __init__(
        self,
        config: RecoveryConfig | None = None,
        *,
        detector: FailureDetector | None = None,
        diagnoser: FailureDiagnoser | None = None,
        planner: RecoveryPlanner | None = None,
        executor: SelfHealingExecutor | None = None,
    ) -> None:
        self.config = config or RecoveryConfig()
        self.detector = detector or FailureDetector(self.config)
        self.diagnoser = diagnoser or FailureDiagnoser()
        self.planner = planner or RecoveryPlanner(self.config)
        self.executor = executor or SelfHealingExecutor()

    def run(
        self,
        *,
        telemetry_state: RealTimeStateSnapshot,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
        optimization_report: OptimizationReport | None = None,
        twin_snapshot: DigitalTwinSnapshot | None = None,
        control_state: ControlState | None = None,
        healing_state: SelfHealingState | None = None,
    ) -> FailureRecoveryReport:
        if twin_snapshot is not None and twin_snapshot.timestamp_s != network_snapshot.timestamp_s:
            raise ValueError("digital twin and network snapshots must have matching timestamps")

        failures = self.detector.detect(
            telemetry_state=telemetry_state,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
            optimization_report=optimization_report,
        )
        diagnoses = self.diagnoser.diagnose(failures)
        plan = self.planner.plan(
            failures,
            diagnoses,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
        )
        results, next_healing_state, next_control_state = self.executor.apply(
            plan,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
            control_state=control_state,
            state=healing_state,
        )
        plan.unresolved_event_ids = sorted(
            event_id
            for event_id in plan.event_ids
            if event_id in next_healing_state.active_event_ids
        )
        all_recovered = all(item.verified for item in results) and not plan.unresolved_event_ids

        for event in failures:
            event.status = (
                event.status
                if event.event_id in plan.unresolved_event_ids
                else FailureStatus.RECOVERED
            )
        return FailureRecoveryReport(
            timestamp_s=network_snapshot.timestamp_s,
            detected_failures=failures,
            diagnoses=diagnoses,
            plan=plan,
            execution_results=results,
            self_healing_state=next_healing_state,
            resulting_control_state=next_control_state,
            all_recovered=all_recovered,
        )


__all__ = ["FailureRecoveryEngine"]
