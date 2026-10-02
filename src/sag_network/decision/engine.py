from __future__ import annotations

import hashlib
import json

from sag_network.decision.models import (
    DecisionAction,
    DecisionActionType,
    DecisionConfig,
    DecisionPriority,
    DecisionReport,
    DecisionStatus,
    SelectedDecision,
)
from sag_network.decision.policy import DecisionPolicy, ExplainablePredictivePolicy
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.predictive.models import PredictiveReport


_PRIORITY_WEIGHT = {
    DecisionPriority.LOW: 1.0,
    DecisionPriority.MEDIUM: 1.25,
    DecisionPriority.HIGH: 1.5,
    DecisionPriority.CRITICAL: 2.0,
}


class DecisionEngine:
    """Deterministic, explainable action-selection engine for predictive warnings."""

    def __init__(
        self,
        config: DecisionConfig | None = None,
        policy: DecisionPolicy | None = None,
    ) -> None:
        self.config = config or DecisionConfig()
        self.policy = policy or ExplainablePredictivePolicy(self.config)

    @staticmethod
    def _decision_id(timestamp_s: float, action: DecisionAction) -> str:
        payload = json.dumps(action.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{timestamp_s:.6f}|{payload}".encode()).hexdigest()[:16]
        return f"decision-{digest}"

    @staticmethod
    def _rank_key(action: DecisionAction) -> tuple[float, int, str, str]:
        return (
            action.utility_score * _PRIORITY_WEIGHT[action.priority],
            int(action.feasible),
            action.action_type.value,
            action.target_source_id,
        )

    def _select(
        self,
        *,
        actions: list[DecisionAction],
        timestamp_s: float,
    ) -> list[SelectedDecision]:
        feasible = [action for action in actions if action.feasible]
        ranked = sorted(feasible, key=self._rank_key, reverse=True)
        selected: list[SelectedDecision] = []
        seen_targets: set[str] = set()
        for action in ranked:
            if len(selected) >= self.config.maximum_actions:
                break
            if action.target_source_id in seen_targets:
                continue
            seen_targets.add(action.target_source_id)
            confidence = min(
                1.0,
                max(
                    evidence.confidence_score
                    for evidence in action.evidence
                ) if action.evidence else 0.0,
            )
            explanation = (
                f"Selected {action.action_type.value} for {action.target_source_id} "
                f"with utility {action.utility_score:.3f}; {action.rationale}."
            )
            selected.append(
                SelectedDecision(
                    action=action,
                    decision_id=self._decision_id(timestamp_s, action),
                    timestamp_s=timestamp_s,
                    status=DecisionStatus.ACTION_SELECTED,
                    confidence_score=confidence,
                    explanation=explanation,
                )
            )
        return selected

    def decide(
        self,
        predictive_report: PredictiveReport,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
    ) -> DecisionReport:
        """Turn predictive warnings into ranked, explainable, bounded action decisions."""
        if predictive_report.timestamp_s != network_snapshot.timestamp_s:
            raise ValueError("predictive and network snapshots must have matching timestamps")
        if scheduling_snapshot is not None and scheduling_snapshot.timestamp_s != predictive_report.timestamp_s:
            raise ValueError("scheduling and predictive snapshots must have matching timestamps")

        actions = self.policy.propose(
            warnings=predictive_report.early_warnings,
            network_snapshot=network_snapshot,
            scheduling_snapshot=scheduling_snapshot,
        )
        selected = self._select(actions=actions, timestamp_s=predictive_report.timestamp_s)

        if not predictive_report.early_warnings:
            status = DecisionStatus.NO_ACTION_REQUIRED
            actions.append(
                DecisionAction(
                    action_type=DecisionActionType.NO_ACTION,
                    target_source_id="network",
                    feasible=True,
                    utility_score=0.0,
                    priority=DecisionPriority.LOW,
                    rationale="no predictive threshold warnings require intervention",
                    evidence=[],
                )
            )
        elif selected:
            status = DecisionStatus.ACTION_SELECTED
        else:
            status = DecisionStatus.ACTION_UNAVAILABLE

        return DecisionReport(
            timestamp_s=predictive_report.timestamp_s,
            status=status,
            selected_decisions=selected,
            candidate_actions=sorted(
                actions,
                key=self._rank_key,
                reverse=True,
            ),
            predictive_warning_count=len(predictive_report.early_warnings),
        )


__all__ = ["DecisionEngine"]
