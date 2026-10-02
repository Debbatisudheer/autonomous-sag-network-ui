from __future__ import annotations

import pytest

from sag_network.decision.learned_policy import LearnedDecisionPolicy
from sag_network.decision.learning_models import (
    DecisionLearningExample,
    LearnedDecisionConfig,
    LearnedDecisionModel,
)
from sag_network.decision.models import (
    DecisionAction,
    DecisionActionType,
    DecisionConfig,
    DecisionEvidence,
    DecisionPriority,
)
from sag_network.decision.policy import ExplainablePredictivePolicy
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.predictive.models import PredictiveEarlyWarning, WarningSeverity
from sag_network.telemetry.models import TelemetryMetric


def _action(action_type: DecisionActionType, utility: float, confidence: float) -> DecisionAction:
    return DecisionAction(
        action_type=action_type,
        target_source_id="uav-a:user-01",
        target_resource_id="uav-a",
        alternative_resource_id="gnd-a" if action_type is not DecisionActionType.RESERVE_SPECTRUM else None,
        target_domain=NetworkDomain.AIR,
        alternative_domain=NetworkDomain.GROUND if action_type is not DecisionActionType.RESERVE_SPECTRUM else None,
        feasible=True,
        utility_score=utility,
        priority=DecisionPriority.HIGH,
        rationale="synthetic learning fixture",
        evidence=[
            DecisionEvidence(
                warning_source_id="uav-a:user-01",
                domain=NetworkDomain.AIR,
                metric="sinr_db",
                severity=WarningSeverity.WARNING,
                predicted_value=8.0,
                threshold_value=10.0,
                lead_time_s=2.0,
                confidence_score=confidence,
                threshold_direction="below_minimum",
            )
        ],
    )


def test_learned_model_is_deterministic() -> None:
    examples = [
        DecisionLearningExample(action=_action(DecisionActionType.PREPARE_HANDOVER, 0.8, 0.9), observed_reward=0.9),
        DecisionLearningExample(action=_action(DecisionActionType.RESERVE_SPECTRUM, 0.7, 0.8), observed_reward=0.8),
        DecisionLearningExample(action=_action(DecisionActionType.REROUTE_FLOW, 0.6, 0.7), observed_reward=0.7),
        DecisionLearningExample(action=_action(DecisionActionType.REDUCE_LOAD, 0.5, 0.6), observed_reward=0.6),
        DecisionLearningExample(action=_action(DecisionActionType.PREPOSITION_RESOURCE, 0.4, 0.5), observed_reward=0.5),
        DecisionLearningExample(action=_action(DecisionActionType.NO_ACTION, 0.1, 0.4), observed_reward=0.2),
    ]
    first = LearnedDecisionModel(LearnedDecisionConfig(ridge_alpha=0.2)).fit(examples)
    second_model = LearnedDecisionModel(LearnedDecisionConfig(ridge_alpha=0.2))
    second = second_model.fit(examples)
    assert first.model_fingerprint == second.model_fingerprint
    assert first.training_rmse == second.training_rmse
    first_prediction = LearnedDecisionModel(LearnedDecisionConfig(ridge_alpha=0.2))
    first_prediction.fit(examples)
    assert second_model.predict_reward(examples[0].action) == pytest.approx(
        first_prediction.predict_reward(examples[0].action)
    )


def test_learning_requires_explicit_examples() -> None:
    model = LearnedDecisionModel(LearnedDecisionConfig(minimum_examples=3))
    with pytest.raises(ValueError, match="at least 3 learning examples"):
        model.fit([DecisionLearningExample(action=_action(DecisionActionType.NO_ACTION, 0.0, 0.5), observed_reward=0.0)])


def test_learned_policy_preserves_baseline_action_contract() -> None:
    examples = [
        DecisionLearningExample(action=_action(DecisionActionType.PREPARE_HANDOVER, 0.8, 0.9), observed_reward=0.9),
        DecisionLearningExample(action=_action(DecisionActionType.RESERVE_SPECTRUM, 0.7, 0.8), observed_reward=0.8),
        DecisionLearningExample(action=_action(DecisionActionType.REROUTE_FLOW, 0.6, 0.7), observed_reward=0.7),
        DecisionLearningExample(action=_action(DecisionActionType.REDUCE_LOAD, 0.5, 0.6), observed_reward=0.6),
        DecisionLearningExample(action=_action(DecisionActionType.PREPOSITION_RESOURCE, 0.4, 0.5), observed_reward=0.5),
        DecisionLearningExample(action=_action(DecisionActionType.NO_ACTION, 0.1, 0.4), observed_reward=0.2),
    ]
    model = LearnedDecisionModel()
    model.fit(examples)
    policy = LearnedDecisionPolicy(model, ExplainablePredictivePolicy(DecisionConfig()))
    candidate = UnifiedCandidate(
        resource_id="uav-a",
        domain=NetworkDomain.AIR,
        resource_type="test",
        available=True,
        distance_m=1000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=6.0,
        link_margin_db=1.5,
        shannon_capacity_bps=50_000_000.0,
        estimated_capacity_bps=50_000_000.0,
        propagation_delay_ms=5.0,
        doppler_shift_hz=0.0,
    )
    alternative = candidate.model_copy(update={"resource_id": "gnd-a", "domain": NetworkDomain.GROUND, "link_margin_db": 8.0})
    snapshot = UnifiedNetworkSnapshot(
        timestamp_s=10.0,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20_000_000.0,
                allocated_capacity_bps=20_000_000.0,
                candidates=[candidate, alternative],
            )
        ],
    )
    warning = PredictiveEarlyWarning(
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
        reason="synthetic warning",
    )
    actions = policy.propose(
        warnings=[warning],
        network_snapshot=snapshot,
        scheduling_snapshot=None,
    )
    assert len(actions) == 1
    assert actions[0].action_type is DecisionActionType.PREPARE_HANDOVER
    assert "learned value=" in actions[0].rationale
    assert 0.0 <= actions[0].utility_score <= 1.0
