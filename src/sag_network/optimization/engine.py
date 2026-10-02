from __future__ import annotations

from sag_network.decision.models import DecisionReport
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.optimization.control import AutonomousControlExecutor
from sag_network.optimization.models import (
    ControlExecutionReport,
    ControlState,
    OptimizationConfig,
    OptimizationPlan,
    OptimizationReport,
)
from sag_network.optimization.optimizer import OptimizationEngine


class AutonomousOptimizationEngine:
    """Closed-loop Phase 19 engine: optimize decisions, apply controls, then verify."""

    def __init__(
        self,
        config: OptimizationConfig | None = None,
        *,
        optimizer: OptimizationEngine | None = None,
        executor: AutonomousControlExecutor | None = None,
    ) -> None:
        self.config = config or OptimizationConfig()
        self.optimizer = optimizer or OptimizationEngine(self.config)
        self.executor = executor or AutonomousControlExecutor()

    def optimize(
        self,
        decision_report: DecisionReport,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
    ) -> OptimizationPlan:
        return self.optimizer.optimize(
            decision_report,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
        )

    def execute(
        self,
        plan: OptimizationPlan,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
        state: ControlState | None = None,
    ) -> ControlExecutionReport:
        return self.executor.apply(
            plan,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
            state=state,
        )

    def run(
        self,
        decision_report: DecisionReport,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
        state: ControlState | None = None,
    ) -> OptimizationReport:
        plan = self.optimize(
            decision_report,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
        )
        execution = self.execute(
            plan,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
            state=state,
        )
        return OptimizationReport(
            timestamp_s=decision_report.timestamp_s,
            plan=plan,
            execution=execution,
        )


__all__ = ["AutonomousOptimizationEngine"]
