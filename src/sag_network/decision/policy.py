from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from sag_network.decision.models import (
    DecisionAction,
    DecisionActionType,
    DecisionConfig,
    DecisionEvidence,
    DecisionPriority,
)
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import UnifiedCandidate, UnifiedNetworkSnapshot
from sag_network.predictive.models import PredictiveEarlyWarning, WarningSeverity


class DecisionPolicy(Protocol):
    """Pluggable policy interface for future learned decision models."""

    def propose(
        self,
        *,
        warnings: Iterable[PredictiveEarlyWarning],
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    ) -> list[DecisionAction]:
        ...


def _priority(severity: WarningSeverity, lead_time_s: float) -> DecisionPriority:
    if severity is WarningSeverity.CRITICAL or lead_time_s <= 2.0:
        return DecisionPriority.CRITICAL
    if severity is WarningSeverity.WARNING or lead_time_s <= 5.0:
        return DecisionPriority.HIGH
    return DecisionPriority.MEDIUM


def _evidence(warning: PredictiveEarlyWarning) -> DecisionEvidence:
    return DecisionEvidence(
        warning_source_id=warning.source_id,
        domain=warning.domain,
        metric=warning.metric.value,
        severity=warning.severity,
        predicted_value=warning.predicted_value,
        threshold_value=warning.threshold_value,
        lead_time_s=warning.lead_time_s,
        confidence_score=warning.confidence_score,
        threshold_direction=warning.threshold_direction,
    )


def _association_for_source(
    snapshot: UnifiedNetworkSnapshot,
    source_id: str,
) -> tuple[str, UnifiedCandidate] | None:
    # Predictive telemetry source ids normally use resource:user. Accept resource-only
    # sources as well so non-user telemetry can still drive protection policies.
    for association in snapshot.associations:
        for candidate in association.candidates:
            if candidate.resource_id == source_id or f"{candidate.resource_id}:{association.user_id}" == source_id:
                return association.user_id, candidate
    return None


def _alternative_candidates(
    snapshot: UnifiedNetworkSnapshot,
    *,
    user_id: str,
    current_resource_id: str,
    config: DecisionConfig,
) -> list[UnifiedCandidate]:
    for association in snapshot.associations:
        if association.user_id != user_id:
            continue
        candidates = [
            candidate
            for candidate in association.candidates
            if candidate.available
            and candidate.resource_id != current_resource_id
            and candidate.link_margin_db >= config.minimum_alternative_margin_db
            and candidate.estimated_capacity_bps > 0
        ]
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.estimated_capacity_bps,
                candidate.link_margin_db,
                candidate.sinr_db,
                candidate.propagation_delay_ms * -1,
                candidate.resource_id,
            ),
            reverse=True,
        )
    return []


def _resource_available_for_reservation(
    scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    resource_id: str,
    config: DecisionConfig,
) -> bool:
    if scheduling_snapshot is None:
        return False
    for utilization in scheduling_snapshot.utilization:
        if utilization.resource_id == resource_id:
            return (
                utilization.utilization_ratio < config.maximum_resource_utilization_ratio
                and utilization.remaining_capacity_bps > 0
            )
    return False


class ExplainablePredictivePolicy:
    """Deterministic baseline policy that converts predictive warnings into actions.

    This is an AI-engine interface baseline, not a trained machine-learning model. The
    policy is intentionally replaceable through the DecisionPolicy protocol.
    """

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self.config = config or DecisionConfig()

    def propose(
        self,
        *,
        warnings: Iterable[PredictiveEarlyWarning],
        network_snapshot: UnifiedNetworkSnapshot,
        scheduling_snapshot: SpectrumSchedulingSnapshot | None,
    ) -> list[DecisionAction]:
        actions: list[DecisionAction] = []
        for warning in warnings:
            if warning.confidence_score < self.config.minimum_confidence:
                continue
            associated = _association_for_source(network_snapshot, warning.source_id)
            if associated is None:
                actions.append(
                    DecisionAction(
                        action_type=DecisionActionType.NO_ACTION,
                        target_source_id=warning.source_id,
                        feasible=False,
                        utility_score=0.0,
                        priority=DecisionPriority.LOW,
                        rationale="predictive warning has no matching network candidate state",
                        evidence=[_evidence(warning)],
                        constraints=["network_state_match_required"],
                    )
                )
                continue

            user_id, current_candidate = associated
            alternatives = _alternative_candidates(
                network_snapshot,
                user_id=user_id,
                current_resource_id=current_candidate.resource_id,
                config=self.config,
            )
            priority = _priority(warning.severity, warning.lead_time_s)
            urgency = 1.0 / (1.0 + warning.lead_time_s)
            confidence = warning.confidence_score
            evidence = [_evidence(warning)]

            if warning.metric.value in {"sinr_db", "link_margin_db", "received_power_dbm"}:
                alternative = alternatives[0] if alternatives else None
                feasible = alternative is not None
                utility = confidence * (1.0 + urgency)
                if alternative is not None:
                    utility += max(alternative.link_margin_db - current_candidate.link_margin_db, 0.0) / 10.0
                    if alternative.domain is not current_candidate.domain:
                        utility -= self.config.handover_domain_change_penalty
                actions.append(
                    DecisionAction(
                        action_type=DecisionActionType.PREPARE_HANDOVER,
                        target_source_id=warning.source_id,
                        target_resource_id=current_candidate.resource_id,
                        alternative_resource_id=alternative.resource_id if alternative else None,
                        target_domain=current_candidate.domain,
                        alternative_domain=alternative.domain if alternative else None,
                        feasible=feasible,
                        utility_score=max(utility, 0.0),
                        priority=priority,
                        rationale=(
                            "predicted radio degradation; an available alternative can be prepared"
                            if feasible
                            else "predicted radio degradation; no feasible alternative is currently available"
                        ),
                        evidence=evidence,
                        constraints=([] if feasible else ["alternative_candidate_required"]),
                    )
                )

            if warning.metric.value == "capacity_bps":
                reserve_feasible = _resource_available_for_reservation(
                    scheduling_snapshot,
                    current_candidate.resource_id,
                    self.config,
                )
                actions.append(
                    DecisionAction(
                        action_type=DecisionActionType.RESERVE_SPECTRUM,
                        target_source_id=warning.source_id,
                        target_resource_id=current_candidate.resource_id,
                        target_domain=current_candidate.domain,
                        feasible=reserve_feasible,
                        utility_score=confidence * (1.0 + urgency),
                        priority=priority,
                        rationale=(
                            "predicted capacity degradation; spectrum reserve remains available"
                            if reserve_feasible
                            else "predicted capacity degradation; no reserve capacity is confirmed"
                        ),
                        evidence=evidence,
                        constraints=([] if reserve_feasible else ["resource_state_required"]),
                    )
                )

            if warning.metric.value in {"latency_ms", "resource_utilization_ratio"}:
                feasible = bool(alternatives)
                action_type = (
                    DecisionActionType.REROUTE_FLOW
                    if warning.metric.value == "latency_ms"
                    else DecisionActionType.REDUCE_LOAD
                )
                alternative = alternatives[0] if alternatives else None
                actions.append(
                    DecisionAction(
                        action_type=action_type,
                        target_source_id=warning.source_id,
                        target_resource_id=current_candidate.resource_id,
                        alternative_resource_id=alternative.resource_id if alternative else None,
                        target_domain=current_candidate.domain,
                        alternative_domain=alternative.domain if alternative else None,
                        feasible=feasible,
                        utility_score=confidence * (0.8 + urgency),
                        priority=priority,
                        rationale=(
                            "predicted service degradation can be mitigated by changing resource pressure"
                            if feasible
                            else "predicted service degradation has no confirmed alternative resource"
                        ),
                        evidence=evidence,
                        constraints=([] if feasible else ["alternative_candidate_required"]),
                    )
                )

            if warning.metric.value in {"remaining_energy_wh", "interference_power_dbm"}:
                alternative = alternatives[0] if alternatives else None
                feasible = alternative is not None
                actions.append(
                    DecisionAction(
                        action_type=DecisionActionType.PREPOSITION_RESOURCE,
                        target_source_id=warning.source_id,
                        target_resource_id=current_candidate.resource_id,
                        alternative_resource_id=alternative.resource_id if alternative else None,
                        target_domain=current_candidate.domain,
                        alternative_domain=alternative.domain if alternative else None,
                        feasible=feasible,
                        utility_score=confidence * (0.7 + urgency),
                        priority=priority,
                        rationale=(
                            "predicted resource stress warrants pre-positioning an alternative resource"
                            if feasible
                            else "predicted resource stress detected without a confirmed alternative"
                        ),
                        evidence=evidence,
                        constraints=([] if feasible else ["alternative_candidate_required"]),
                    )
                )

        return actions


__all__ = ["DecisionPolicy", "ExplainablePredictivePolicy"]
