from __future__ import annotations

import json

from sag_network.decision.learned_policy import LearnedDecisionPolicy
from sag_network.decision.learning_models import (
    DecisionLearningExample,
    LearnedDecisionConfig,
    LearnedDecisionModel,
)
from sag_network.decision.models import (
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


def _action(action_type: DecisionActionType, utility: float, confidence: float) -> object:
    from sag_network.decision.models import DecisionAction

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
        rationale="synthetic historical decision outcome fixture",
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


def _training_examples() -> list[DecisionLearningExample]:
    return [
        DecisionLearningExample(action=_action(DecisionActionType.PREPARE_HANDOVER, 0.90, 0.95), observed_reward=0.94),
        DecisionLearningExample(action=_action(DecisionActionType.PREPARE_HANDOVER, 0.70, 0.80), observed_reward=0.78),
        DecisionLearningExample(action=_action(DecisionActionType.RESERVE_SPECTRUM, 0.85, 0.90), observed_reward=0.86),
        DecisionLearningExample(action=_action(DecisionActionType.RESERVE_SPECTRUM, 0.60, 0.70), observed_reward=0.66),
        DecisionLearningExample(action=_action(DecisionActionType.REROUTE_FLOW, 0.80, 0.85), observed_reward=0.79),
        DecisionLearningExample(action=_action(DecisionActionType.REROUTE_FLOW, 0.55, 0.65), observed_reward=0.60),
        DecisionLearningExample(action=_action(DecisionActionType.REDUCE_LOAD, 0.70, 0.80), observed_reward=0.71),
        DecisionLearningExample(action=_action(DecisionActionType.REDUCE_LOAD, 0.45, 0.60), observed_reward=0.55),
        DecisionLearningExample(action=_action(DecisionActionType.PREPOSITION_RESOURCE, 0.65, 0.75), observed_reward=0.64),
        DecisionLearningExample(action=_action(DecisionActionType.PREPOSITION_RESOURCE, 0.40, 0.55), observed_reward=0.49),
        DecisionLearningExample(action=_action(DecisionActionType.NO_ACTION, 0.10, 0.40), observed_reward=0.18),
        DecisionLearningExample(action=_action(DecisionActionType.NO_ACTION, 0.05, 0.30), observed_reward=0.12),
    ]


def _snapshot() -> UnifiedNetworkSnapshot:
    current = UnifiedCandidate(
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
    alternative = current.model_copy(
        update={
            "resource_id": "gnd-a",
            "domain": NetworkDomain.GROUND,
            "link_margin_db": 8.0,
            "sinr_db": 13.0,
            "estimated_capacity_bps": 100_000_000.0,
        }
    )
    return UnifiedNetworkSnapshot(
        timestamp_s=10.0,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20_000_000.0,
                allocated_capacity_bps=20_000_000.0,
                candidates=[current, alternative],
            )
        ],
    )


def main() -> None:
    examples = _training_examples()
    model = LearnedDecisionModel(LearnedDecisionConfig(ridge_alpha=0.1, minimum_examples=6, learning_weight=0.7))
    training = model.fit(examples)
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
        reason="synthetic phase36 warning",
    )
    policy = LearnedDecisionPolicy(model, ExplainablePredictivePolicy(DecisionConfig()))
    actions = policy.propose(
        warnings=[warning],
        network_snapshot=_snapshot(),
        scheduling_snapshot=None,
    )
    selected = max((action for action in actions if action.feasible), key=lambda action: action.utility_score, default=None)
    payload = {
        "name": "Learned Decision Engine",
        "phase": "36",
        "status": "pass" if selected is not None else "fail",
        "training_examples": training.example_count,
        "feature_count": training.feature_count,
        "training_rmse": training.training_rmse,
        "model_fingerprint": training.model_fingerprint,
        "candidate_action_count": len(actions),
        "learned_action": selected.action_type.value if selected else None,
        "learned_utility": selected.utility_score if selected else None,
        "fixture": "synthetic historical decision-outcome fixture",
        "state_mutation": False,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
