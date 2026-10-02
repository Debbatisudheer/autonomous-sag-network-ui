from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.decision.engine import DecisionEngine
from sag_network.decision.models import DecisionConfig, DecisionPriority, DecisionStatus
from sag_network.domain.resource import ResourceUtilization, SpectrumSchedulingSnapshot
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.optimization.control import AutonomousControlExecutor
from sag_network.optimization.engine import AutonomousOptimizationEngine
from sag_network.optimization.models import (
    ControlAction,
    ControlActionStatus,
    ControlActionType,
    ControlState,
    OptimizationConfig,
    OptimizationObjective,
    OptimizationPlan,
)
from sag_network.predictive.models import PredictiveEarlyWarning, PredictiveReport, WarningSeverity
from sag_network.telemetry.models import TelemetryMetric


def candidate(
    resource_id: str,
    *,
    margin: float,
    capacity: float,
    latency_ms: float = 5.0,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.GROUND if resource_id.startswith("gnd") else NetworkDomain.AIR,
        resource_type="test",
        available=True,
        distance_m=1000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=margin + 5.0,
        link_margin_db=margin,
        shannon_capacity_bps=capacity,
        estimated_capacity_bps=capacity,
        propagation_delay_ms=latency_ms,
        doppler_shift_hz=0.0,
    )


def snapshot(timestamp_s: float = 10.0) -> UnifiedNetworkSnapshot:
    return UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20e6,
                allocated_capacity_bps=20e6,
                candidates=[
                    candidate("uav-a", margin=1.5, capacity=40e6, latency_ms=20.0),
                    candidate("gnd-a", margin=10.0, capacity=100e6, latency_ms=5.0),
                ],
            )
        ],
    )


def warning() -> PredictiveEarlyWarning:
    return PredictiveEarlyWarning(
        source_id="uav-a:user-01",
        domain=NetworkDomain.AIR,
        metric=TelemetryMetric.SINR_DB,
        severity=WarningSeverity.CRITICAL,
        forecast_timestamp_s=11.0,
        lead_time_s=1.0,
        predicted_value=8.0,
        threshold_value=10.0,
        threshold_direction="below_minimum",
        confidence_score=0.9,
        reason="predicted threshold violation",
    )


def decision_report(timestamp_s: float = 10.0):
    return DecisionEngine(DecisionConfig()).decide(
        PredictiveReport(timestamp_s=timestamp_s, early_warnings=[warning()]),
        network_snapshot=snapshot(timestamp_s),
    )


def scheduling(timestamp_s: float = 10.0) -> SpectrumSchedulingSnapshot:
    return SpectrumSchedulingSnapshot(
        timestamp_s=timestamp_s,
        allocations=[],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a",
                total_resource_blocks=20,
                used_resource_blocks=18,
                free_resource_blocks=2,
                utilization_ratio=0.9,
                scheduled_capacity_bps=36e6,
                remaining_capacity_bps=4e6,
            ),
            ResourceUtilization(
                resource_id="gnd-a",
                total_resource_blocks=20,
                used_resource_blocks=5,
                free_resource_blocks=15,
                utilization_ratio=0.25,
                scheduled_capacity_bps=25e6,
                remaining_capacity_bps=75e6,
            ),
        ],
    )


def test_balanced_optimizer_selects_feasible_handover() -> None:
    report = AutonomousOptimizationEngine().run(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    assert report.plan.selected_actions
    action = report.plan.selected_actions[0]
    assert action.action_type is ControlActionType.PREPARE_HANDOVER
    assert action.alternative_resource_id == "gnd-a"


def test_plan_objective_is_positive_for_useful_action() -> None:
    plan = AutonomousOptimizationEngine().optimize(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    assert plan.objective_value > 0


def test_control_executor_records_handover_preparation() -> None:
    report = AutonomousOptimizationEngine().run(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    result = report.execution.results[0]
    assert result.status is ControlActionStatus.VERIFIED
    assert report.execution.resulting_state.prepared_handover_targets["uav-a:user-01"] == "gnd-a"
    assert report.execution.all_verified


def test_control_action_uses_configured_load_reduction_ratio() -> None:
    decision = decision_report()
    plan = AutonomousOptimizationEngine(
        OptimizationConfig(load_reduction_ratio=0.25)
    ).optimize(decision, network_snapshot=snapshot())
    assert plan.selected_actions[0].load_reduction_ratio == pytest.approx(0.25)


def test_empty_decision_report_produces_empty_verified_cycle() -> None:
    decision = DecisionEngine().decide(
        PredictiveReport(timestamp_s=10.0),
        network_snapshot=snapshot(),
    )
    report = AutonomousOptimizationEngine().run(decision, network_snapshot=snapshot())
    assert decision.status is DecisionStatus.NO_ACTION_REQUIRED
    assert report.plan.selected_actions == []
    assert report.execution.all_verified


def test_timestamp_alignment_is_required() -> None:
    with pytest.raises(ValueError, match="matching timestamps"):
        AutonomousOptimizationEngine().optimize(
            decision_report(10.0),
            network_snapshot=snapshot(11.0),
        )


def test_scheduling_timestamp_alignment_is_required() -> None:
    with pytest.raises(ValueError, match="matching timestamps"):
        AutonomousOptimizationEngine().optimize(
            decision_report(10.0),
            network_snapshot=snapshot(10.0),
            scheduling_snapshot=scheduling(11.0),
        )


def test_control_state_can_be_carried_between_cycles() -> None:
    engine = AutonomousOptimizationEngine()
    first = engine.run(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    second_state = first.execution.resulting_state.model_copy(update={"timestamp_s": 11.0})
    second = engine.run(
        decision_report(11.0),
        network_snapshot=snapshot(11.0),
        scheduling_snapshot=scheduling(11.0),
        state=second_state,
    )
    assert second.execution.resulting_state.version == second_state.version + 1
    assert second.execution.resulting_state.prepared_handover_targets["uav-a:user-01"] == "gnd-a"


def test_newer_control_state_is_rejected() -> None:
    state = ControlState(timestamp_s=12.0)
    with pytest.raises(ValueError, match="cannot be newer"):
        AutonomousControlExecutor().apply(
            AutonomousOptimizationEngine().optimize(
                decision_report(),
                network_snapshot=snapshot(),
            ),
            network_snapshot=snapshot(),
            state=state,
        )


def test_maximum_actions_bounds_selection() -> None:
    config = OptimizationConfig(maximum_actions=1)
    plan = AutonomousOptimizationEngine(config).optimize(
        decision_report(),
        network_snapshot=snapshot(),
    )
    assert len(plan.selected_actions) <= 1


def test_resource_utilization_constraint_can_reject_alternative() -> None:
    constrained = scheduling()
    constrained.utilization[1].utilization_ratio = 0.95
    plan = AutonomousOptimizationEngine(
        OptimizationConfig(maximum_resource_utilization_ratio=0.9)
    ).optimize(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=constrained,
    )
    assert not plan.selected_actions or plan.selected_actions[0].feasible is True
    assert any(
        "maximum_resource_utilization_exceeded" in action.constraints
        for action in plan.candidate_actions
    )


def test_minimum_capacity_ratio_can_reject_action() -> None:
    weak = snapshot()
    weak.associations[0].candidates[1] = candidate(
        "gnd-a",
        margin=10.0,
        capacity=10e6,
        latency_ms=5.0,
    )
    plan = AutonomousOptimizationEngine(
        OptimizationConfig(minimum_capacity_ratio=0.5)
    ).optimize(
        decision_report(),
        network_snapshot=weak,
    )
    assert any(
        "minimum_capacity_ratio_required" in action.constraints
        for action in plan.candidate_actions
    )


def test_control_reservation_is_verified() -> None:
    decision = DecisionEngine().decide(
        PredictiveReport(
            timestamp_s=10.0,
            early_warnings=[warning().model_copy(update={"metric": TelemetryMetric.CAPACITY_BPS})],
        ),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    report = AutonomousOptimizationEngine().run(
        decision,
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    assert all(item.verified for item in report.execution.results)


def test_control_state_rejects_duplicate_reservations() -> None:
    with pytest.raises(ValidationError, match="reserved_resource_ids"):
        ControlState(timestamp_s=0.0, reserved_resource_ids=["gnd-a", "gnd-a"])


def test_control_state_rejects_duplicate_prepositioning() -> None:
    with pytest.raises(ValidationError, match="prepositioned_resource_ids"):
        ControlState(timestamp_s=0.0, prepositioned_resource_ids=["gnd-a", "gnd-a"])


def test_objective_enum_is_configurable() -> None:
    config = OptimizationConfig(objective=OptimizationObjective.MINIMIZE_LATENCY)
    assert config.objective is OptimizationObjective.MINIMIZE_LATENCY


def test_objective_changes_score() -> None:
    balanced = AutonomousOptimizationEngine(
        OptimizationConfig(objective=OptimizationObjective.BALANCED_UTILITY)
    ).optimize(decision_report(), network_snapshot=snapshot())
    capacity = AutonomousOptimizationEngine(
        OptimizationConfig(objective=OptimizationObjective.MAXIMIZE_CAPACITY)
    ).optimize(decision_report(), network_snapshot=snapshot())
    assert capacity.objective_value > balanced.objective_value


def test_reroute_action_updates_selected_resource() -> None:
    action = ControlAction(
        action_id="control-reroute",
        action_type=ControlActionType.REROUTE_FLOW,
        source_id="user-01",
        target_resource_id="uav-a",
        alternative_resource_id="gnd-a",
        timestamp_s=10.0,
        feasible=True,
        priority=DecisionPriority.HIGH,
        decision_utility=1.0,
        expected_gain=1.0,
        objective_score=1.0,
        rationale="reroute test",
    )
    plan = OptimizationPlan(
        timestamp_s=10.0,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=1.0,
        candidate_actions=[action],
        selected_actions=[action],
    )
    report = AutonomousControlExecutor().apply(plan, network_snapshot=snapshot())
    assert report.all_verified
    assert report.resulting_state.selected_resources["user-01"] == "gnd-a"
    assert report.resulting_state.rerouted_sources["user-01"] == "gnd-a"


def test_reduce_load_action_uses_action_ratio() -> None:
    action = ControlAction(
        action_id="control-load",
        action_type=ControlActionType.REDUCE_LOAD,
        source_id="uav-a:user-01",
        target_resource_id="uav-a",
        timestamp_s=10.0,
        feasible=True,
        priority=DecisionPriority.HIGH,
        decision_utility=1.0,
        expected_gain=0.5,
        objective_score=1.0,
        load_reduction_ratio=0.25,
        rationale="load reduction test",
    )
    plan = OptimizationPlan(
        timestamp_s=10.0,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=1.0,
        candidate_actions=[action],
        selected_actions=[action],
    )
    report = AutonomousControlExecutor().apply(plan, network_snapshot=snapshot())
    assert report.all_verified
    assert report.resulting_state.load_reduction_ratios["uav-a:user-01"] == pytest.approx(0.25)


def test_preposition_action_requires_an_available_resource() -> None:
    action = ControlAction(
        action_id="control-preposition",
        action_type=ControlActionType.PREPOSITION_RESOURCE,
        source_id="uav-a:user-01",
        target_resource_id="uav-a",
        alternative_resource_id="gnd-a",
        timestamp_s=10.0,
        feasible=True,
        priority=DecisionPriority.MEDIUM,
        decision_utility=1.0,
        expected_gain=1.0,
        objective_score=1.0,
        rationale="preposition test",
    )
    plan = OptimizationPlan(
        timestamp_s=10.0,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=1.0,
        candidate_actions=[action],
        selected_actions=[action],
    )
    report = AutonomousControlExecutor().apply(plan, network_snapshot=snapshot())
    assert report.all_verified
    assert report.resulting_state.prepositioned_resource_ids == ["gnd-a"]


def test_deterministic_control_action_ids() -> None:
    first = AutonomousOptimizationEngine().optimize(
        decision_report(), network_snapshot=snapshot(), scheduling_snapshot=scheduling()
    )
    second = AutonomousOptimizationEngine().optimize(
        decision_report(), network_snapshot=snapshot(), scheduling_snapshot=scheduling()
    )
    assert [action.action_id for action in first.candidate_actions] == [
        action.action_id for action in second.candidate_actions
    ]


def test_plan_selection_is_deterministic() -> None:
    engine = AutonomousOptimizationEngine()
    first = engine.run(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    second = engine.run(
        decision_report(),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(),
    )
    assert first.plan.model_dump() == second.plan.model_dump()
    assert (
        first.execution.resulting_state.model_dump()
        == second.execution.resulting_state.model_dump()
    )
