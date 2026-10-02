from __future__ import annotations

from sag_network.optimization.models import (
    ControlAction,
    ControlActionType,
    OptimizationObjective,
    OptimizationPlan,
)
from sag_network.planning import AutonomousMultiStepPlanner, PlanningConfig


def action(
    action_id: str, action_type: ControlActionType, source: str, score: float
) -> ControlAction:
    return ControlAction(
        action_id=action_id,
        action_type=action_type,
        source_id=source,
        alternative_resource_id="uav-a",
        timestamp_s=10.0,
        feasible=True,
        priority="high",
        decision_utility=score,
        expected_gain=score,
        objective_score=score,
        rationale="synthetic test action",
    )


def plan(actions: list[ControlAction]) -> OptimizationPlan:
    return OptimizationPlan(
        timestamp_s=10.0,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=0.0,
        candidate_actions=actions,
        selected_actions=[],
    )


def test_planner_orders_dependencies() -> None:
    result = AutonomousMultiStepPlanner(PlanningConfig(maximum_steps=3)).plan(
        plan(
            [
                action("reroute", ControlActionType.REROUTE_FLOW, "u1", 3.0),
                action("prepare", ControlActionType.PREPARE_HANDOVER, "u1", 2.0),
                action("preposition", ControlActionType.PREPOSITION_RESOURCE, "u1", 1.0),
            ]
        )
    )
    assert result.verified
    assert [step.action.action_id for step in result.steps] == [
        "preposition",
        "prepare",
        "reroute",
    ]
    assert result.steps[2].depends_on == ("prepare",)


def test_planner_can_combine_independent_actions() -> None:
    result = AutonomousMultiStepPlanner(PlanningConfig(maximum_steps=2)).plan(
        plan(
            [
                action("load", ControlActionType.REDUCE_LOAD, "u2", 2.0),
                action("reserve", ControlActionType.RESERVE_SPECTRUM, "u1", 1.5),
            ]
        )
    )
    assert result.verified
    assert len(result.steps) == 2


def test_planner_is_deterministic() -> None:
    source = plan(
        [
            action("b", ControlActionType.REDUCE_LOAD, "u2", 1.0),
            action("a", ControlActionType.RESERVE_SPECTRUM, "u1", 1.0),
        ]
    )
    planner = AutonomousMultiStepPlanner(PlanningConfig(maximum_steps=2))
    assert planner.plan(source) == planner.plan(source)


def test_infeasible_actions_are_excluded() -> None:
    candidate = action(
        "bad", ControlActionType.REDUCE_LOAD, "u1", 4.0
    ).model_copy(update={"feasible": False})
    result = AutonomousMultiStepPlanner().plan(plan([candidate]))
    assert result.steps == ()
    assert result.verified
