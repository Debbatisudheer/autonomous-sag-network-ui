from __future__ import annotations

import hashlib
import json

from sag_network.decision.models import DecisionAction, DecisionPriority, DecisionReport
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import (
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.optimization.models import (
    ControlAction,
    ControlActionType,
    OptimizationConfig,
    OptimizationPlan,
)

_PRIORITY_WEIGHT = {
    DecisionPriority.LOW: 1.0,
    DecisionPriority.MEDIUM: 1.2,
    DecisionPriority.HIGH: 1.5,
    DecisionPriority.CRITICAL: 2.0,
}


def _find_association(
    snapshot: UnifiedNetworkSnapshot, source_id: str
) -> UnifiedUserAssociation | None:
    for association in snapshot.associations:
        for candidate in association.candidates:
            if (
                candidate.resource_id == source_id
                or f"{candidate.resource_id}:{association.user_id}" == source_id
            ):
                return association
    return None


def _find_candidate(
    snapshot: UnifiedNetworkSnapshot,
    user_id: str,
    resource_id: str | None,
) -> UnifiedCandidate | None:
    if resource_id is None:
        return None
    for association in snapshot.associations:
        if association.user_id != user_id:
            continue
        return next(
            (
                candidate
                for candidate in association.candidates
                if candidate.resource_id == resource_id
            ),
            None,
        )
    return None


def _resource_utilization(
    scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    resource_id: str | None,
) -> float:
    if scheduling_snapshot is None or resource_id is None:
        return 0.0
    for utilization in scheduling_snapshot.utilization:
        if utilization.resource_id == resource_id:
            return utilization.utilization_ratio
    return 1.0


def _capacity_gain(
    current: UnifiedCandidate | None, alternative: UnifiedCandidate | None
) -> float:
    if current is None or alternative is None or current.estimated_capacity_bps <= 0:
        return 0.0
    return max(
        0.0,
        (alternative.estimated_capacity_bps - current.estimated_capacity_bps)
        / current.estimated_capacity_bps,
    )


def _margin_gain(
    current: UnifiedCandidate | None, alternative: UnifiedCandidate | None
) -> float:
    if current is None or alternative is None:
        return 0.0
    return max(0.0, alternative.link_margin_db - current.link_margin_db) / 10.0


def _latency_gain(
    current: UnifiedCandidate | None, alternative: UnifiedCandidate | None
) -> float:
    if current is None or alternative is None or current.propagation_delay_ms <= 0:
        return 0.0
    return max(
        0.0,
        (current.propagation_delay_ms - alternative.propagation_delay_ms)
        / current.propagation_delay_ms,
    )


def _balance_gain(
    scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    current_resource_id: str | None,
    alternative_resource_id: str | None,
) -> float:
    current = _resource_utilization(scheduling_snapshot, current_resource_id)
    alternative = _resource_utilization(scheduling_snapshot, alternative_resource_id)
    return max(0.0, current - alternative)


def _action_id(action: DecisionAction, timestamp_s: float, score: float) -> str:
    payload = {
        "decision_id": action.model_dump(mode="json"),
        "timestamp_s": round(timestamp_s, 6),
        "score": round(score, 9),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"control-{hashlib.sha256(encoded).hexdigest()[:16]}"


class OptimizationEngine:
    """Deterministic constrained optimizer over Phase 18 decision proposals."""

    def __init__(self, config: OptimizationConfig | None = None) -> None:
        self.config = config or OptimizationConfig()

    def _build_action(
        self,
        action: DecisionAction,
        *,
        timestamp_s: float,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    ) -> ControlAction:
        association = _find_association(network_snapshot, action.target_source_id)
        user_id = association.user_id if association is not None else action.target_source_id
        current_resource_id = (
            association.selected_resource_id
            if association is not None
            else action.target_resource_id
        )
        current = _find_candidate(network_snapshot, user_id, current_resource_id)
        alternative = _find_candidate(network_snapshot, user_id, action.alternative_resource_id)

        capacity_gain = _capacity_gain(current, alternative)
        margin_gain = _margin_gain(current, alternative)
        latency_gain = _latency_gain(current, alternative)
        balance_gain = _balance_gain(
            scheduling_snapshot,
            current_resource_id,
            action.alternative_resource_id,
        )
        priority_gain = _PRIORITY_WEIGHT[action.priority]

        objective_score = (
            self.config.decision_utility_weight * action.utility_score
            + self.config.priority_weight * priority_gain
            + self.config.capacity_gain_weight * capacity_gain
            + self.config.margin_gain_weight * margin_gain
            + self.config.latency_gain_weight * latency_gain
            + self.config.resource_balance_weight * balance_gain
        )

        if action.alternative_resource_id and current_resource_id:
            objective_score -= self.config.switching_cost
        if (
            action.target_domain is not None
            and action.alternative_domain is not None
            and action.target_domain is not action.alternative_domain
        ):
            objective_score -= self.config.domain_change_cost

        constraints = list(action.constraints)
        feasible = action.feasible
        if alternative is not None and alternative.estimated_capacity_bps > 0:
            if current is not None and current.estimated_capacity_bps > 0:
                capacity_ratio = alternative.estimated_capacity_bps / current.estimated_capacity_bps
                if capacity_ratio < self.config.minimum_capacity_ratio:
                    feasible = False
                    constraints.append("minimum_capacity_ratio_required")
            if not alternative.available:
                feasible = False
                constraints.append("alternative_resource_must_be_available")
        if action.alternative_resource_id is not None:
            utilization = _resource_utilization(scheduling_snapshot, action.alternative_resource_id)
            if utilization > self.config.maximum_resource_utilization_ratio:
                feasible = False
                constraints.append("maximum_resource_utilization_exceeded")

        objective_bonus = {
            "balanced_utility": 0.0,
            "maximize_capacity": self.config.capacity_gain_weight * capacity_gain,
            "maximize_link_margin": self.config.margin_gain_weight * margin_gain,
            "minimize_latency": self.config.latency_gain_weight * latency_gain,
            "balance_resources": self.config.resource_balance_weight * balance_gain,
        }[self.config.objective.value]
        objective_score = max(0.0, objective_score + objective_bonus)
        expected_gain = capacity_gain + margin_gain + latency_gain + balance_gain
        return ControlAction(
            action_id=_action_id(action, timestamp_s, objective_score),
            action_type=ControlActionType(action.action_type.value),
            source_id=action.target_source_id,
            target_resource_id=current_resource_id,
            alternative_resource_id=action.alternative_resource_id,
            target_domain=action.target_domain,
            alternative_domain=action.alternative_domain,
            timestamp_s=timestamp_s,
            feasible=feasible,
            priority=action.priority,
            decision_utility=action.utility_score,
            expected_gain=max(0.0, expected_gain),
            objective_score=objective_score,
            rationale=action.rationale,
            constraints=sorted(set(constraints)),
            load_reduction_ratio=self.config.load_reduction_ratio,
        )

    def _objective_sort_key(self, action: ControlAction) -> tuple[float, int, float, str]:
        return (
            action.objective_score,
            int(action.feasible),
            action.expected_gain,
            action.action_id,
        )

    def optimize(
        self,
        decision_report: DecisionReport,
        *,
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None = None,
    ) -> OptimizationPlan:
        if decision_report.timestamp_s != network_snapshot.timestamp_s:
            raise ValueError("decision and network snapshots must have matching timestamps")
        if scheduling_snapshot is not None and (
            scheduling_snapshot.timestamp_s != decision_report.timestamp_s
        ):
            raise ValueError("scheduling and decision snapshots must have matching timestamps")

        candidates = [
            self._build_action(
                selected.action,
                timestamp_s=decision_report.timestamp_s,
                network_snapshot=network_snapshot,
                scheduling_snapshot=scheduling_snapshot,
            )
            for selected in decision_report.selected_decisions
            if selected.action.action_type.value != "no_action"
        ]
        candidates.extend(
            self._build_action(
                action,
                timestamp_s=decision_report.timestamp_s,
                network_snapshot=network_snapshot,
                scheduling_snapshot=scheduling_snapshot,
            )
            for action in decision_report.candidate_actions
            if action.feasible
            and action.action_type.value != "no_action"
            and action.target_source_id
            not in {
                selected.action.target_source_id
                for selected in decision_report.selected_decisions
            }
        )

        deduplicated: dict[str, ControlAction] = {
            action.action_id: action for action in candidates
        }
        ordered = sorted(deduplicated.values(), key=self._objective_sort_key, reverse=True)
        selected: list[ControlAction] = []
        selected_targets: set[str] = set()
        rejected: list[str] = []
        objective_value = 0.0

        for action in ordered:
            if not action.feasible:
                rejected.append(action.action_id)
                continue
            if action.objective_score < self.config.minimum_expected_gain:
                rejected.append(action.action_id)
                continue
            if len(selected) >= self.config.maximum_actions:
                rejected.append(action.action_id)
                continue
            if action.source_id in selected_targets:
                rejected.append(action.action_id)
                continue
            selected.append(action)
            selected_targets.add(action.source_id)
            objective_value += action.objective_score

        return OptimizationPlan(
            timestamp_s=decision_report.timestamp_s,
            objective=self.config.objective,
            objective_value=objective_value,
            candidate_actions=ordered,
            selected_actions=selected,
            rejected_action_ids=sorted(rejected),
            constraints=[
                f"maximum_actions={self.config.maximum_actions}",
                (
                    "maximum_resource_utilization_ratio="
                    f"{self.config.maximum_resource_utilization_ratio:.3f}"
                ),
            ],
        )


__all__ = ["OptimizationEngine"]
