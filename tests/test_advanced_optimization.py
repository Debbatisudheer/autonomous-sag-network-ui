from __future__ import annotations

from sag_network.decision.models import DecisionPriority
from sag_network.optimization.advanced import (
    AdvancedOptimizationConfig,
    AdvancedOptimizationEngine,
)
from sag_network.optimization.models import (
    ControlAction,
    ControlActionType,
    OptimizationObjective,
    OptimizationPlan,
)


def action(
    action_id: str,
    *,
    source_id: str,
    resource_id: str,
    score: float,
    gain: float,
) -> ControlAction:
    return ControlAction(
        action_id=action_id,
        action_type=ControlActionType.REROUTE_FLOW,
        source_id=source_id,
        target_resource_id=f"current-{source_id}",
        alternative_resource_id=resource_id,
        timestamp_s=10.0,
        feasible=True,
        priority=DecisionPriority.HIGH,
        decision_utility=score,
        expected_gain=gain,
        objective_score=score,
        rationale="phase37 test action",
    )


def plan(*actions_: ControlAction) -> OptimizationPlan:
    return OptimizationPlan(
        timestamp_s=10.0,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=sum(item.objective_score for item in actions_),
        candidate_actions=list(actions_),
    )


def test_pareto_frontier_removes_dominated_actions() -> None:
    engine = AdvancedOptimizationEngine()
    frontier = engine.pareto_frontier(
        [
            action("a", source_id="u1", resource_id="r1", score=1.0, gain=1.0),
            action("b", source_id="u2", resource_id="r2", score=0.5, gain=0.5),
            action("c", source_id="u3", resource_id="r3", score=0.8, gain=1.2),
        ]
    )
    assert [item.action_id for item in frontier] == ["a", "c"]


def test_search_respects_one_action_per_source() -> None:
    engine = AdvancedOptimizationEngine()
    result = engine.optimize(
        plan(
            action("a", source_id="u1", resource_id="r1", score=2.0, gain=1.0),
            action("b", source_id="u1", resource_id="r2", score=1.0, gain=2.0),
            action("c", source_id="u2", resource_id="r3", score=1.5, gain=2.0),
        )
    )
    assert {item.source_id for item in result.selected_actions} == {"u1", "u2"}


def test_search_respects_resource_concentration_limit() -> None:
    engine = AdvancedOptimizationEngine(
        AdvancedOptimizationConfig(maximum_actions_per_resource=1)
    )
    result = engine.optimize(
        plan(
            action("a", source_id="u1", resource_id="r1", score=2.0, gain=1.0),
            action("b", source_id="u2", resource_id="r1", score=1.9, gain=1.0),
            action("c", source_id="u3", resource_id="r2", score=1.0, gain=1.0),
        )
    )
    assert sum(item.alternative_resource_id == "r1" for item in result.selected_actions) == 1


def test_search_is_deterministic() -> None:
    engine = AdvancedOptimizationEngine()
    source = plan(
        action("a", source_id="u1", resource_id="r1", score=1.0, gain=1.0),
        action("b", source_id="u2", resource_id="r2", score=1.0, gain=1.0),
        action("c", source_id="u3", resource_id="r3", score=0.9, gain=1.1),
    )
    first = engine.optimize(source)
    second = engine.optimize(source)
    assert first == second


def test_empty_plan_is_safe() -> None:
    result = AdvancedOptimizationEngine().optimize(plan())
    assert result.selected_actions == ()
    assert result.objective_value == 0.0
    assert result.search_states == 1
