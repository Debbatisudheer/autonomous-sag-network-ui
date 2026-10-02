from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.decision.models import DecisionAction, DecisionActionType, DecisionPriority


class LearningFeature(str, Enum):
    """Stable feature names used by the Phase 36 learned value model."""

    BIAS = "bias"
    BASE_UTILITY = "base_utility"
    FEASIBLE = "feasible"
    PRIORITY = "priority"
    CONFIDENCE = "confidence"
    URGENCY = "urgency"
    ALTERNATIVE_PRESENT = "alternative_present"
    CONSTRAINT_COUNT = "constraint_count"
    ACTION_PREPARE_HANDOVER = "action_prepare_handover"
    ACTION_RESERVE_SPECTRUM = "action_reserve_spectrum"
    ACTION_REROUTE_FLOW = "action_reroute_flow"
    ACTION_REDUCE_LOAD = "action_reduce_load"
    ACTION_PREPOSITION_RESOURCE = "action_preposition_resource"
    ACTION_NO_ACTION = "action_no_action"


class DecisionLearningExample(BaseModel):
    """One historical decision/action outcome used as supervised learning evidence."""

    action: DecisionAction
    observed_reward: float = Field(ge=0, le=1)


class LearnedDecisionConfig(BaseModel):
    """Deterministic configuration for the learned decision value model."""

    ridge_alpha: float = Field(default=0.1, gt=0)
    minimum_examples: int = Field(default=6, ge=2)
    learning_weight: float = Field(default=0.7, ge=0, le=1)


class LearnedDecisionReport(BaseModel):
    """Training metadata and deterministic model fingerprint."""

    example_count: int = Field(ge=0)
    feature_count: int = Field(ge=1)
    training_rmse: float = Field(ge=0)
    model_fingerprint: str = Field(min_length=64, max_length=64)
    feature_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_feature_count(self) -> LearnedDecisionReport:
        if self.feature_count != len(self.feature_names):
            raise ValueError("feature_count must match feature_names length")
        return self


_PRIORITY_VALUE = {
    DecisionPriority.LOW: 0.25,
    DecisionPriority.MEDIUM: 0.5,
    DecisionPriority.HIGH: 0.75,
    DecisionPriority.CRITICAL: 1.0,
}

_ACTION_FEATURES = {
    DecisionActionType.PREPARE_HANDOVER: LearningFeature.ACTION_PREPARE_HANDOVER,
    DecisionActionType.RESERVE_SPECTRUM: LearningFeature.ACTION_RESERVE_SPECTRUM,
    DecisionActionType.REROUTE_FLOW: LearningFeature.ACTION_REROUTE_FLOW,
    DecisionActionType.REDUCE_LOAD: LearningFeature.ACTION_REDUCE_LOAD,
    DecisionActionType.PREPOSITION_RESOURCE: LearningFeature.ACTION_PREPOSITION_RESOURCE,
    DecisionActionType.NO_ACTION: LearningFeature.ACTION_NO_ACTION,
}

FEATURE_NAMES = [feature.value for feature in LearningFeature]


def action_features(action: DecisionAction) -> list[float]:
    """Convert one decision action into a stable numeric feature vector."""
    confidence = max(
        (evidence.confidence_score for evidence in action.evidence),
        default=0.0,
    )
    lead_time = min(
        (evidence.lead_time_s for evidence in action.evidence),
        default=0.0,
    )
    action_feature = _ACTION_FEATURES[action.action_type]
    return [
        1.0,
        action.utility_score,
        float(action.feasible),
        _PRIORITY_VALUE[action.priority],
        confidence,
        1.0 / (1.0 + max(lead_time, 0.0)),
        float(action.alternative_resource_id is not None),
        min(len(action.constraints), 10) / 10.0,
        float(action_feature is LearningFeature.ACTION_PREPARE_HANDOVER),
        float(action_feature is LearningFeature.ACTION_RESERVE_SPECTRUM),
        float(action_feature is LearningFeature.ACTION_REROUTE_FLOW),
        float(action_feature is LearningFeature.ACTION_REDUCE_LOAD),
        float(action_feature is LearningFeature.ACTION_PREPOSITION_RESOURCE),
        float(action_feature is LearningFeature.ACTION_NO_ACTION),
    ]


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small dense linear system using deterministic Gauss-Jordan elimination."""
    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("learning matrix is singular")
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            augmented[row] = [
                left - factor * right
                for left, right in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[row][-1] for row in range(size)]


class LearnedDecisionModel:
    """Small deterministic ridge-regression value model for decision actions."""

    def __init__(self, config: LearnedDecisionConfig | None = None) -> None:
        self._config = config or LearnedDecisionConfig()
        self._coefficients: list[float] | None = None
        self._report: LearnedDecisionReport | None = None

    @property
    def is_fitted(self) -> bool:
        return self._coefficients is not None

    @property
    def config(self) -> LearnedDecisionConfig:
        return self._config

    @property
    def report(self) -> LearnedDecisionReport:
        if self._report is None:
            raise RuntimeError("learned decision model has not been fitted")
        return self._report

    def fit(self, examples: Iterable[DecisionLearningExample]) -> LearnedDecisionReport:
        rows = list(examples)
        if len(rows) < self._config.minimum_examples:
            raise ValueError(
                f"at least {self._config.minimum_examples} learning examples are required"
            )
        feature_rows = [action_features(example.action) for example in rows]
        feature_count = len(FEATURE_NAMES)
        matrix = [[0.0 for _ in range(feature_count)] for _ in range(feature_count)]
        vector = [0.0 for _ in range(feature_count)]
        for features, example in zip(feature_rows, rows, strict=True):
            for row in range(feature_count):
                vector[row] += features[row] * example.observed_reward
                for column in range(feature_count):
                    matrix[row][column] += features[row] * features[column]
        for index in range(feature_count):
            matrix[index][index] += self._config.ridge_alpha
        coefficients = _solve_linear_system(matrix, vector)
        predictions = [
            self._clip(sum(coefficient * feature for coefficient, feature in zip(coefficients, features, strict=True)))
            for features in feature_rows
        ]
        rmse = math.sqrt(
            sum((prediction - example.observed_reward) ** 2 for prediction, example in zip(predictions, rows, strict=True))
            / len(rows)
        )
        fingerprint_payload = {
            "config": self._config.model_dump(mode="json"),
            "feature_names": FEATURE_NAMES,
            "coefficients": [round(value, 15) for value in coefficients],
            "example_count": len(rows),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self._coefficients = coefficients
        self._report = LearnedDecisionReport(
            example_count=len(rows),
            feature_count=feature_count,
            training_rmse=rmse,
            model_fingerprint=fingerprint,
            feature_names=FEATURE_NAMES,
        )
        return self._report

    def predict_reward(self, action: DecisionAction) -> float:
        if self._coefficients is None:
            raise RuntimeError("learned decision model has not been fitted")
        features = action_features(action)
        return self._clip(
            sum(
                coefficient * feature
                for coefficient, feature in zip(self._coefficients, features, strict=True)
            )
        )

    @staticmethod
    def _clip(value: float) -> float:
        return max(0.0, min(1.0, value))


__all__ = [
    "FEATURE_NAMES",
    "DecisionLearningExample",
    "LearnedDecisionConfig",
    "LearnedDecisionModel",
    "LearnedDecisionReport",
    "LearningFeature",
    "action_features",
]
