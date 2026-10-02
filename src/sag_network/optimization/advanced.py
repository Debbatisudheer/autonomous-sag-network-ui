from __future__ import annotations

from dataclasses import dataclass

from sag_network.optimization.models import ControlAction, OptimizationPlan


@dataclass(frozen=True, slots=True)
class AdvancedOptimizationConfig:
    """Deterministic bounded-search controls for Phase 37 optimization."""

    maximum_actions: int = 5
    beam_width: int = 16
    maximum_actions_per_resource: int = 2
    diversity_bonus: float = 0.1
    expected_gain_weight: float = 0.25

    def __post_init__(self) -> None:
        if self.maximum_actions < 1:
            raise ValueError("maximum_actions must be positive")
        if self.beam_width < 1:
            raise ValueError("beam_width must be positive")
        if self.maximum_actions_per_resource < 1:
            raise ValueError("maximum_actions_per_resource must be positive")
        if self.diversity_bonus < 0 or self.expected_gain_weight < 0:
            raise ValueError("optimization weights must be non-negative")


@dataclass(frozen=True, slots=True)
class AdvancedOptimizationResult:
    """Immutable result of the Phase 37 bounded multi-objective search."""

    selected_actions: tuple[ControlAction, ...]
    objective_value: float
    pareto_frontier_ids: tuple[str, ...]
    search_states: int


@dataclass(frozen=True, slots=True)
class _SearchState:
    actions: tuple[ControlAction, ...]
    sources: frozenset[str]
    resource_counts: tuple[tuple[str, int], ...]
    score: float

    @property
    def resource_count_map(self) -> dict[str, int]:
        return dict(self.resource_counts)


class AdvancedOptimizationEngine:
    """Bounded deterministic multi-objective search over a Phase 19 plan.

    The Phase 19 optimizer remains responsible for generating feasible actions and
    applying its existing hard constraints. Phase 37 only improves the selection
    of those already-generated actions; it never mutates network state.
    """

    def __init__(self, config: AdvancedOptimizationConfig | None = None) -> None:
        self.config = config or AdvancedOptimizationConfig()

    @staticmethod
    def _dominates(left: ControlAction, right: ControlAction) -> bool:
        return (
            left.objective_score >= right.objective_score
            and left.expected_gain >= right.expected_gain
            and (
                left.objective_score > right.objective_score
                or left.expected_gain > right.expected_gain
            )
        )

    def pareto_frontier(self, actions: list[ControlAction]) -> list[ControlAction]:
        """Return deterministic non-dominated feasible actions."""
        feasible = [action for action in actions if action.feasible]
        frontier = [
            action
            for action in feasible
            if not any(
                other.action_id != action.action_id and self._dominates(other, action)
                for other in feasible
            )
        ]
        return sorted(
            frontier,
            key=lambda action: (
                -action.objective_score,
                -action.expected_gain,
                action.action_id,
            ),
        )

    def _state_score(
        self,
        actions: tuple[ControlAction, ...],
        resource_counts: dict[str, int],
    ) -> float:
        objective = sum(action.objective_score for action in actions)
        expected_gain = sum(action.expected_gain for action in actions)
        distinct_resources = len(resource_counts)
        return (
            objective
            + self.config.expected_gain_weight * expected_gain
            + self.config.diversity_bonus * distinct_resources
        )

    @staticmethod
    def _sort_key(state: _SearchState) -> tuple[float, float, tuple[str, ...]]:
        return (
            -state.score,
            -sum(action.expected_gain for action in state.actions),
            tuple(action.action_id for action in state.actions),
        )

    def optimize(self, plan: OptimizationPlan) -> AdvancedOptimizationResult:
        """Search feasible actions with source/resource conflict constraints."""
        frontier = self.pareto_frontier(plan.candidate_actions)
        if not frontier:
            return AdvancedOptimizationResult((), 0.0, (), 1)

        initial = _SearchState((), frozenset(), (), 0.0)
        beam = [initial]
        states_seen = 1
        best = initial

        for _ in range(self.config.maximum_actions):
            expanded: list[_SearchState] = []
            for state in beam:
                selected_ids = {action.action_id for action in state.actions}
                counts = state.resource_count_map
                for action in frontier:
                    if action.action_id in selected_ids or action.source_id in state.sources:
                        continue
                    resource_id = action.alternative_resource_id or action.target_resource_id
                    next_counts = dict(counts)
                    if resource_id is not None:
                        next_counts[resource_id] = next_counts.get(resource_id, 0) + 1
                        if (
                            next_counts[resource_id]
                            > self.config.maximum_actions_per_resource
                        ):
                            continue
                    actions = tuple(
                        sorted((*state.actions, action), key=lambda item: item.action_id)
                    )
                    score = self._state_score(actions, next_counts)
                    expanded.append(
                        _SearchState(
                            actions=actions,
                            sources=state.sources | {action.source_id},
                            resource_counts=tuple(sorted(next_counts.items())),
                            score=score,
                        )
                    )

            if not expanded:
                break
            states_seen += len(expanded)
            beam = sorted(expanded, key=self._sort_key)[: self.config.beam_width]
            if self._sort_key(beam[0]) < self._sort_key(best):
                best = beam[0]

        return AdvancedOptimizationResult(
            selected_actions=best.actions,
            objective_value=best.score,
            pareto_frontier_ids=tuple(action.action_id for action in frontier),
            search_states=states_seen,
        )


__all__ = [
    "AdvancedOptimizationConfig",
    "AdvancedOptimizationEngine",
    "AdvancedOptimizationResult",
]
