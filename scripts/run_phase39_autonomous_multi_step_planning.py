from __future__ import annotations

import json

from sag_network.optimization.models import (
    ControlAction,
    ControlActionType,
    OptimizationObjective,
    OptimizationPlan,
)
from sag_network.planning import AutonomousMultiStepPlanner, PlanningConfig


def main() -> None:
    timestamp_s = 120.0
    actions = [
        ControlAction(
            action_id="preposition-uav",
            action_type=ControlActionType.PREPOSITION_RESOURCE,
            source_id="user-01",
            target_resource_id="uav-a",
            timestamp_s=timestamp_s,
            feasible=True,
            priority="high",
            decision_utility=0.7,
            expected_gain=1.2,
            objective_score=2.0,
            rationale="prepare the air resource",
        ),
        ControlAction(
            action_id="prepare-handover",
            action_type=ControlActionType.PREPARE_HANDOVER,
            source_id="user-01",
            alternative_resource_id="uav-a",
            timestamp_s=timestamp_s,
            feasible=True,
            priority="high",
            decision_utility=0.8,
            expected_gain=1.5,
            objective_score=2.5,
            rationale="prepare the handover",
        ),
        ControlAction(
            action_id="reroute-user",
            action_type=ControlActionType.REROUTE_FLOW,
            source_id="user-01",
            alternative_resource_id="uav-a",
            timestamp_s=timestamp_s,
            feasible=True,
            priority="high",
            decision_utility=0.9,
            expected_gain=2.0,
            objective_score=3.0,
            rationale="move the flow after preparation",
        ),
        ControlAction(
            action_id="reduce-load",
            action_type=ControlActionType.REDUCE_LOAD,
            source_id="user-02",
            target_resource_id="gnd-a",
            timestamp_s=timestamp_s,
            feasible=True,
            priority="medium",
            decision_utility=0.5,
            expected_gain=0.8,
            objective_score=1.4,
            rationale="reduce congestion on ground resource",
        ),
    ]
    plan = OptimizationPlan(
        timestamp_s=timestamp_s,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=0.0,
        candidate_actions=actions,
        selected_actions=[],
    )
    result = AutonomousMultiStepPlanner(PlanningConfig(maximum_steps=3)).plan(plan)
    print(
        json.dumps(
            {
                "name": "Autonomous Multi-Step Planning",
                "phase": "39",
                "status": "pass" if result.verified else "fail",
                "candidate_action_count": len(actions),
                "plan_step_count": len(result.steps),
                "steps": [
                    {
                        "step": step.step_index,
                        "action": step.action.action_id,
                        "depends_on": list(step.depends_on),
                    }
                    for step in result.steps
                ],
                "objective_value": result.objective_value,
                "plan_verified": result.verified,
                "state_mutation": False,
                "fixture": "synthetic autonomous planning fixture",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
