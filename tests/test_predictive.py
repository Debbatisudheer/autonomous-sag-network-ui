from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.domain.unified import NetworkDomain
from sag_network.predictive.engine import PredictiveIntelligenceEngine
from sag_network.predictive.features import extract_features
from sag_network.predictive.forecast import forecast_history
from sag_network.predictive.models import (
    ForecastMethod,
    PredictionStatus,
    PredictiveConfig,
    PredictiveThresholdRule,
    WarningSeverity,
)
from sag_network.predictive.risk import evaluate_early_warnings
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def record(
    *,
    record_id: str,
    timestamp_s: float,
    sequence: int,
    value: float,
    metric: TelemetryMetric = TelemetryMetric.SINR_DB,
    source_id: str = "uav-a:user-01",
) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=sequence,
        source_id=source_id,
        domain=NetworkDomain.AIR,
        metric=metric,
        value=value,
        unit="dB" if metric is TelemetryMetric.SINR_DB else "bit/s",
    )


def linear_history(
    values: list[float],
    *,
    metric: TelemetryMetric = TelemetryMetric.SINR_DB,
) -> list[TelemetryRecord]:
    return [
        record(
            record_id=f"r-{index}",
            timestamp_s=float(index),
            sequence=index,
            value=value,
            metric=metric,
        )
        for index, value in enumerate(values, start=1)
    ]


def test_feature_extraction_computes_basic_statistics() -> None:
    features = extract_features(linear_history([20.0, 17.0, 14.0, 11.0]), reference_time_s=4.0)
    feature = features[0]
    assert feature.sample_count == 4
    assert feature.latest_value == 11.0
    assert feature.minimum_value == 11.0
    assert feature.maximum_value == 20.0
    assert feature.mean_value == pytest.approx(15.5)
    assert feature.trend_per_s == pytest.approx(-3.0)
    assert feature.last_delta_per_s == pytest.approx(-3.0)
    assert feature.trend_r_squared == pytest.approx(1.0)


def test_feature_extraction_marks_stale_input() -> None:
    config = PredictiveConfig(max_input_age_s=2.0)
    features = extract_features(linear_history([20.0, 17.0, 14.0]), reference_time_s=8.0, config=config)
    assert features[0].stale is True
    assert features[0].age_s == pytest.approx(5.0)


def test_feature_extraction_respects_history_window() -> None:
    config = PredictiveConfig(history_window=3)
    features = extract_features(linear_history([30.0, 20.0, 10.0, 8.0]), reference_time_s=4.0, config=config)
    assert features[0].sample_count == 3
    assert features[0].minimum_value == 8.0


def test_forecast_linear_trend_is_deterministic() -> None:
    config = PredictiveConfig(horizon_steps=2, step_s=1.0)
    history = linear_history([20.0, 17.0, 14.0, 11.0])
    first = forecast_history(history, reference_time_s=4.0, config=config)
    second = forecast_history(history, reference_time_s=4.0, config=config)
    assert first == second
    assert [point.predicted_value for point in first[0].points] == pytest.approx([8.0, 5.0])


def test_forecast_uses_last_value_when_configured() -> None:
    config = PredictiveConfig(
        method=ForecastMethod.LAST_VALUE,
        horizon_steps=2,
        step_s=2.0,
    )
    series = forecast_history(linear_history([20.0, 17.0, 14.0]), reference_time_s=3.0, config=config)[0]
    assert [point.predicted_value for point in series.points] == [14.0, 14.0]
    assert all(point.method is ForecastMethod.LAST_VALUE for point in series.points)


def test_forecast_rejects_stale_input_by_default() -> None:
    config = PredictiveConfig(max_input_age_s=1.0)
    series = forecast_history(linear_history([20.0, 17.0, 14.0]), reference_time_s=5.0, config=config)[0]
    assert series.status is PredictionStatus.STALE_INPUT
    assert series.points == []


def test_stale_input_can_be_allowed() -> None:
    config = PredictiveConfig(max_input_age_s=1.0, reject_stale_inputs=False)
    series = forecast_history(linear_history([20.0, 17.0, 14.0]), reference_time_s=5.0, config=config)[0]
    assert series.status is PredictionStatus.READY
    assert series.points


def test_forecast_reports_insufficient_history() -> None:
    config = PredictiveConfig(min_points=4)
    series = forecast_history(linear_history([20.0, 17.0, 14.0]), reference_time_s=3.0, config=config)[0]
    assert series.status is PredictionStatus.INSUFFICIENT_HISTORY
    assert "minimum sample count" in (series.reason or "")


def test_forecast_confidence_increases_with_more_consistent_history() -> None:
    short = forecast_history(
        linear_history([20.0, 17.0, 14.0]),
        reference_time_s=3.0,
        config=PredictiveConfig(horizon_steps=1),
    )[0].points[0].confidence_score
    long = forecast_history(
        linear_history([26.0, 23.0, 20.0, 17.0, 14.0, 11.0, 8.0, 5.0, 2.0, -1.0]),
        reference_time_s=10.0,
        config=PredictiveConfig(horizon_steps=1),
    )[0].points[0].confidence_score
    assert long > short


def test_non_linear_history_produces_bounded_r_squared() -> None:
    features = extract_features(linear_history([10.0, 15.0, 11.0, 16.0]), reference_time_s=4.0)
    assert 0.0 <= features[0].trend_r_squared <= 1.0


def test_forecast_future_timestamps_are_monotonic() -> None:
    config = PredictiveConfig(horizon_steps=4, step_s=0.5)
    series = forecast_history(linear_history([20.0, 17.0, 14.0]), reference_time_s=3.0, config=config)[0]
    timestamps = [point.forecast_timestamp_s for point in series.points]
    assert timestamps == sorted(timestamps)
    assert timestamps == pytest.approx([3.5, 4.0, 4.5, 5.0])


def test_predictive_threshold_requires_bound() -> None:
    with pytest.raises(ValidationError, match="threshold bound"):
        PredictiveThresholdRule(metric=TelemetryMetric.SINR_DB)


def test_predictive_threshold_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError, match="minimum_value"):
        PredictiveThresholdRule(
            metric=TelemetryMetric.SINR_DB,
            minimum_value=20.0,
            maximum_value=10.0,
        )


def test_predictive_threshold_rejects_invalid_lead_time_order() -> None:
    with pytest.raises(ValidationError, match="critical_within_s"):
        PredictiveThresholdRule(
            metric=TelemetryMetric.SINR_DB,
            minimum_value=10.0,
            warning_within_s=2.0,
            critical_within_s=3.0,
        )


def test_risk_engine_detects_predicted_minimum_crossing() -> None:
    config = PredictiveConfig(horizon_steps=3, step_s=1.0)
    forecasts = forecast_history(linear_history([20.0, 17.0, 14.0, 11.0]), reference_time_s=4.0, config=config)
    warnings = evaluate_early_warnings(
        forecasts,
        reference_time_s=4.0,
        rules=[
            PredictiveThresholdRule(
                metric=TelemetryMetric.SINR_DB,
                minimum_value=10.0,
                warning_within_s=5.0,
                critical_within_s=2.0,
                minimum_confidence=0.5,
            )
        ],
    )
    assert len(warnings) == 1
    assert warnings[0].severity is WarningSeverity.CRITICAL
    assert warnings[0].forecast_timestamp_s == pytest.approx(5.0)
    assert warnings[0].predicted_value == pytest.approx(8.0)
    assert warnings[0].threshold_direction == "below_minimum"


def test_risk_engine_detects_predicted_maximum_crossing() -> None:
    config = PredictiveConfig(horizon_steps=2)
    history = linear_history(
        [0.5, 0.6, 0.7, 0.8],
        metric=TelemetryMetric.RESOURCE_UTILIZATION_RATIO,
    )
    forecasts = forecast_history(history, reference_time_s=4.0, config=config)
    warnings = evaluate_early_warnings(
        forecasts,
        reference_time_s=4.0,
        rules=[
            PredictiveThresholdRule(
                metric=TelemetryMetric.RESOURCE_UTILIZATION_RATIO,
                maximum_value=0.85,
            )
        ],
    )
    assert len(warnings) == 1
    assert warnings[0].threshold_direction == "above_maximum"


def test_risk_engine_respects_source_specific_rule() -> None:
    forecasts = forecast_history(
        linear_history([20.0, 17.0, 14.0, 11.0],),
        reference_time_s=4.0,
        config=PredictiveConfig(horizon_steps=1),
    )
    warnings = evaluate_early_warnings(
        forecasts,
        reference_time_s=4.0,
        rules=[
            PredictiveThresholdRule(
                source_id="other-source",
                metric=TelemetryMetric.SINR_DB,
                minimum_value=10.0,
            )
        ],
    )
    assert warnings == []


def test_risk_engine_respects_confidence_floor() -> None:
    config = PredictiveConfig(horizon_steps=1)
    forecasts = forecast_history(linear_history([20.0, 17.0, 14.0]), reference_time_s=3.0, config=config)
    warnings = evaluate_early_warnings(
        forecasts,
        reference_time_s=3.0,
        rules=[
            PredictiveThresholdRule(
                metric=TelemetryMetric.SINR_DB,
                minimum_value=15.0,
                minimum_confidence=1.0,
            )
        ],
    )
    assert warnings == []


def test_engine_returns_features_forecasts_and_warnings() -> None:
    engine = PredictiveIntelligenceEngine(PredictiveConfig(horizon_steps=2))
    report = engine.analyze(
        linear_history([20.0, 17.0, 14.0, 11.0]),
        reference_time_s=4.0,
        rules=[
            PredictiveThresholdRule(
                metric=TelemetryMetric.SINR_DB,
                minimum_value=10.0,
            )
        ],
    )
    assert report.timestamp_s == 4.0
    assert len(report.features) == 1
    assert len(report.forecasts) == 1
    assert report.warning_count == 1


def test_engine_is_deterministic() -> None:
    engine = PredictiveIntelligenceEngine(PredictiveConfig(horizon_steps=2))
    history = linear_history([20.0, 17.0, 14.0, 11.0])
    rules = [PredictiveThresholdRule(metric=TelemetryMetric.SINR_DB, minimum_value=10.0)]
    first = engine.analyze(history, reference_time_s=4.0, rules=rules)
    second = engine.analyze(history, reference_time_s=4.0, rules=rules)
    assert first == second


def test_engine_handles_multiple_metrics_independently() -> None:
    sinr = linear_history([20.0, 18.0, 16.0, 14.0], metric=TelemetryMetric.SINR_DB)
    capacity = linear_history(
        [120.0, 110.0, 100.0, 90.0],
        metric=TelemetryMetric.CAPACITY_BPS,
    )
    combined = sinr + [
        item.model_copy(update={"record_id": f"cap-{item.sequence}", "value": item.value * 1_000_000})
        for item in capacity
    ]
    report = PredictiveIntelligenceEngine().analyze(combined, reference_time_s=4.0)
    assert {(feature.source_id, feature.metric) for feature in report.features} == {
        ("uav-a:user-01", TelemetryMetric.SINR_DB),
        ("uav-a:user-01", TelemetryMetric.CAPACITY_BPS),
    }


def test_last_value_prediction_has_bounded_confidence() -> None:
    series = forecast_history(
        linear_history([20.0, 17.0, 14.0]),
        reference_time_s=3.0,
        config=PredictiveConfig(method=ForecastMethod.LAST_VALUE),
    )[0]
    assert all(0.0 <= point.confidence_score <= 0.6 for point in series.points)
