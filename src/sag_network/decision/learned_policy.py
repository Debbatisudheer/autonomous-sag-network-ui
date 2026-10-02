from __future__ import annotations

from collections.abc import Iterable

from sag_network.decision.learning_models import LearnedDecisionModel
from sag_network.decision.models import DecisionAction
from sag_network.decision.policy import ExplainablePredictivePolicy
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.predictive.models import PredictiveEarlyWarning


class LearnedDecisionPolicy:
    """Learned value re-ranking layered over the validated Phase 18 policy baseline."""

    def __init__(
        self,
        model: LearnedDecisionModel,
        baseline: ExplainablePredictivePolicy | None = None,
    ) -> None:
        self.model = model
        self.baseline = baseline or ExplainablePredictivePolicy()

    def propose(
        self,
        *,
        warnings: Iterable[PredictiveEarlyWarning],
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    ) -> list[DecisionAction]:
        actions = self.baseline.propose(
            warnings=warnings,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
        )
        weight = self.model.config.learning_weight
        for action in actions:
            learned_reward = self.model.predict_reward(action)
            action.utility_score = max(
                0.0,
                (1.0 - weight) * min(action.utility_score, 1.0)
                + weight * learned_reward,
            )
            action.rationale = (
                f"{action.rationale}; learned value={learned_reward:.3f}"
            )
        return actions


__all__ = ["LearnedDecisionPolicy"]
