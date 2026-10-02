from __future__ import annotations

from sag_network.domain.unified import NetworkDomain
from sag_network.predictive.deep_learning_models import DeepLearningConfig
from sag_network.predictive.failure_intelligence import PredictiveFailureIntelligence
from sag_network.predictive.failure_models import (
    FailureDirection,
    FailureRiskLevel,
    FailureThresholdRule,
)
from sag_network.predictive.uncertainty import UncertaintyAwarePrediction
from sag_network.predictive.uncertainty_models import UncertaintyConfig
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def history(values: list[float]) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"failure-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:failure-01",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=value,
            unit="dB",
        )
        for index, value in enumerate(values, start=1)
    ]


def report() -> object:
    return UncertaintyAwarePrediction(
        UncertaintyConfig(confidence_level=0.9, minimum_calibration_samples=5),
        DeepLearningConfig(lag_steps=6, minimum_samples=20, hidden_units=6, epochs=60, horizon_steps=3),
    ).predict(history([35.0 - 0.6 * index for index in range(40)]), reference_time_s=40.0)


def test_failure_intelligence_is_deterministic() -> None:
    rules = [
        FailureThresholdRule(
            metric=TelemetryMetric.SINR_DB,
            minimum_value=20.0,
            warning_within_s=5.0,
            critical_within_s=2.0,
        )
    ]
    engine = PredictiveFailureIntelligence()
    first = engine.analyze(report(), reference_time_s=40.0, rules=rules)
    second = engine.analyze(report(), reference_time_s=40.0, rules=rules)
    assert first == second
    assert first.predicted_failure_count > 0


def test_failure_crossing_contains_uncertainty_and_stable_id() -> None:
    result = PredictiveFailureIntelligence().analyze(
        report(),
        reference_time_s=40.0,
        rules=[FailureThresholdRule(metric=TelemetryMetric.SINR_DB, minimum_value=20.0)],
    )
    finding = result.series[0].predicted_failures[0]
    assert finding.direction is FailureDirection.BELOW_MINIMUM
    assert finding.risk_level in set(FailureRiskLevel)
    assert len(finding.event_id) == 64
    assert finding.lower_bound <= finding.predicted_value <= finding.upper_bound
    assert 0.0 <= finding.risk_score <= 1.0


def test_failure_intelligence_ignores_non_matching_rules() -> None:
    result = PredictiveFailureIntelligence().analyze(
        report(),
        reference_time_s=40.0,
        rules=[FailureThresholdRule(metric=TelemetryMetric.LATENCY_MS, maximum_value=10.0)],
    )
    assert result.predicted_failure_count == 0
