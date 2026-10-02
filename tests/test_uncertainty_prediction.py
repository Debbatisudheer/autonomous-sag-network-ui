from __future__ import annotations

from sag_network.domain.unified import NetworkDomain
from sag_network.predictive.deep_learning_models import DeepLearningConfig
from sag_network.predictive.uncertainty import UncertaintyAwarePrediction
from sag_network.predictive.uncertainty_models import UncertaintyConfig, UncertaintyStatus
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def history(values: list[float]) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"unc-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:unc-01",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=value,
            unit="dB",
        )
        for index, value in enumerate(values, start=1)
    ]


def test_uncertainty_prediction_is_deterministic_and_bounded() -> None:
    records = history([30.0 - 0.35 * index + 0.15 * (index % 4) for index in range(40)])
    engine = UncertaintyAwarePrediction(
        UncertaintyConfig(confidence_level=0.9, minimum_calibration_samples=5),
        DeepLearningConfig(lag_steps=6, minimum_samples=20, hidden_units=6, epochs=60, horizon_steps=3),
    )
    first = engine.predict(records, reference_time_s=40.0)
    second = engine.predict(records, reference_time_s=40.0)
    assert first == second
    series = first.series[0]
    assert series.status is UncertaintyStatus.CALIBRATED
    assert series.calibration_samples >= 5
    assert series.calibration_quantile is not None
    assert len(series.intervals) == 3
    for interval in series.intervals:
        assert interval.lower_bound <= interval.predicted_value <= interval.upper_bound
        assert interval.interval_width >= 0
        assert 0.0 <= interval.uncertainty_score <= 1.0


def test_uncertainty_intervals_widen_with_horizon() -> None:
    records = history([25.0 + 0.2 * index + 0.1 * (index % 3) for index in range(40)])
    result = UncertaintyAwarePrediction(
        UncertaintyConfig(confidence_level=0.9, minimum_calibration_samples=5, horizon_growth=0.5),
        DeepLearningConfig(lag_steps=5, minimum_samples=20, hidden_units=4, epochs=50, horizon_steps=3),
    ).predict(records, reference_time_s=40.0)
    intervals = result.series[0].intervals
    assert intervals[0].interval_width < intervals[1].interval_width < intervals[2].interval_width


def test_uncertainty_reports_insufficient_calibration() -> None:
    records = history([20.0 + index for index in range(25)])
    result = UncertaintyAwarePrediction(
        UncertaintyConfig(minimum_calibration_samples=100),
        DeepLearningConfig(lag_steps=5, minimum_samples=10, hidden_units=4, epochs=20),
    ).predict(records, reference_time_s=25.0)
    assert result.series[0].status is UncertaintyStatus.INSUFFICIENT_CALIBRATION
    assert result.series[0].intervals == []


def test_uncertainty_reports_insufficient_history() -> None:
    result = UncertaintyAwarePrediction(
        UncertaintyConfig(minimum_calibration_samples=2),
        DeepLearningConfig(lag_steps=5, minimum_samples=20, epochs=20),
    ).predict(history([1.0, 2.0, 3.0, 4.0, 5.0]), reference_time_s=5.0)
    assert result.series[0].status is UncertaintyStatus.INSUFFICIENT_HISTORY
