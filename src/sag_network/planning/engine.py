from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from sag_network.optimization.models import ControlAction, ControlActionType, OptimizationPlan


class PlanStepStatus(str, Enum):
    """Lifecycle state for one planned autonomous action."""

    PLANNED = "planned"
    VERIFIED = "verified"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    """Deterministic bounds for multi-step plan search."""

    maximum_steps: int = 5
    beam_width: int = 12
    minimum_objective_score: float = 0.0

    def __post_init__(self) -> None:
        if self.maximum_steps < 1:
            raise ValueError("maximum_steps must be positive")
        if self.beam_width < 1:
            raise ValueError("beam_width must be positive")
        if self.minimum_objective_score < 0:
            raise ValueError("minimum_objective_score must be non-negative")


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One deterministic step in an autonomous action sequence."""

    step_index: int
    action: ControlAction
    depends_on: tuple[str, ...]
    status: PlanStepStatus = PlanStepStatus.PLANNED


@dataclass(frozen=True, slots=True)
class AutonomousPlan:
    """Immutable multi-step plan with explicit dependency edges."""

    timestamp_s: float
    steps: tuple[PlanStep, ...]
    objective_value: float
    verified: bool


@dataclass(frozen=True, slots=True)
class _PlanState:
    actions: tuple[ControlAction, ...]
    score: float


class AutonomousMultiStepPlanner:
    """Build deterministic bounded plans from already-feasible control actions.

    The planner does not execute actions or mutate network state. It only orders
    compatible control actions and makes dependencies explicit for a later executor.
    """

    _DEPENDENCIES: ClassVar[dict[ControlActionType, tuple[frozenset[ControlActionType], ...]]] = {
        ControlActionType.PREPARE_HANDOVER: (
            frozenset({ControlActionType.PREPOSITION_RESOURCE}),
            frozenset({ControlActionType.RESERVE_SPECTRUM}),
        ),
        ControlActionType.REROUTE_FLOW: (
            frozenset({ControlActionType.PREPARE_HANDOVER}),
            frozenset({ControlActionType.RESERVE_SPECTRUM}),
        ),
        ControlActionType.REDUCE_LOAD: (),
        ControlActionType.PREPOSITION_RESOURCE: (),
        ControlActionType.RESERVE_SPECTRUM: (),
        ControlActionType.NO_ACTION: (),
    }

    def __init__(self, config: PlanningConfig | None = None) -> None:
        self.config = config or PlanningConfig()

    @classmethod
    def _compatible(cls, existing: tuple[ControlAction, ...], candidate: ControlAction) -> bool:
        if candidate.action_type is ControlActionType.NO_ACTION:
            return False
        for action in existing:
            if action.action_id == candidate.action_id:
                return False
            if action.source_id == candidate.source_id and {
                action.action_type,
                candidate.action_type,
            } == {
                ControlActionType.REROUTE_FLOW,
                ControlActionType.REDUCE_LOAD,
            }:
                return False
        return True

    @classmethod
    def _dependencies(
        cls, actions: tuple[ControlAction, ...], candidate: ControlAction
    ) -> tuple[str, ...] | None:
        alternatives = cls._DEPENDENCIES[candidate.action_type]
        if not alternatives:
            return ()
        available = {action.action_type: action.action_id for action in actions}
        satisfied = [
            alternative
            for alternative in alternatives
            if alternative.issubset(available.keys())
        ]
        if not satisfied:
            return None
        required = min(satisfied, key=lambda items: tuple(sorted(item.value for item in items)))
        return tuple(sorted(available[item] for item in required))

    @staticmethod
    def _score(actions: tuple[ControlAction, ...]) -> float:
        return sum(action.objective_score + action.expected_gain for action in actions)

    @staticmethod
    def _sort_key(state: _PlanState) -> tuple[float, int, tuple[str, ...]]:
        return (
            -state.score,
            -len(state.actions),
            tuple(action.action_id for action in state.actions),
        )

    def plan(self, optimization_plan: OptimizationPlan) -> AutonomousPlan:
        candidates = sorted(
            (
                action
                for action in optimization_plan.candidate_actions
                if action.feasible
                and action.objective_score >= self.config.minimum_objective_score
                and action.action_type is not ControlActionType.NO_ACTION
            ),
            key=lambda action: action.action_id,
        )
        beam = [_PlanState((), 0.0)]
        best = beam[0]

        for _ in range(self.config.maximum_steps):
            expanded: list[_PlanState] = []
            for state in beam:
                for candidate in candidates:
                    if not self._compatible(state.actions, candidate):
                        continue
                    if self._dependencies(state.actions, candidate) is None:
                        continue
                    actions = (*state.actions, candidate)
                    expanded.append(_PlanState(actions, self._score(actions)))
            if not expanded:
                break
            beam = sorted(expanded, key=self._sort_key)[: self.config.beam_width]
            if self._sort_key(beam[0]) < self._sort_key(best):
                best = beam[0]

        steps: list[PlanStep] = []
        for index, action in enumerate(best.actions, start=1):
            dependencies = self._dependencies(best.actions[: index - 1], action)
            if dependencies is None:
                raise RuntimeError("planner produced an unresolved dependency")
            steps.append(PlanStep(index, action, dependencies))
        result = AutonomousPlan(
            timestamp_s=optimization_plan.timestamp_s,
            steps=tuple(steps),
            objective_value=best.score,
            verified=self.verify_steps(tuple(steps)),
        )
        return result

    @classmethod
    def verify_steps(cls, steps: tuple[PlanStep, ...]) -> bool:
        seen: set[str] = set()
        for expected_index, step in enumerate(steps, start=1):
            if step.step_index != expected_index or not step.action.feasible:
                return False
            if step.action.action_id in seen:
                return False
            if not set(step.depends_on).issubset(seen):
                return False
            prior_actions = tuple(item.action for item in steps[: expected_index - 1])
            if cls._dependencies(prior_actions, step.action) is None:
                return False
            seen.add(step.action.action_id)
        return True


__all__ = [
    "AutonomousMultiStepPlanner",
    "AutonomousPlan",
    "PlanStep",
    "PlanStepStatus",
    "PlanningConfig",
]
