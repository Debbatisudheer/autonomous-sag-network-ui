from __future__ import annotations

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.predictive.ml_baseline import MLPredictiveBaseline
from sag_network.predictive.ml_models import MLBaselineConfig, MLBaselineStatus
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def history(values: list[float]) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"ml-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:ml-01",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=value,
            unit="dB",
        )
        for index, value in enumerate(values, start=1)
    ]


def test_ml_baseline_trains_and_forecasts_deterministically() -> None:
    config = MLBaselineConfig(lag_steps=3, minimum_samples=8, horizon_steps=3)
    records = history([20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0, 10.0, 9.0])
    baseline = MLPredictiveBaseline(config)
    first = baseline.train_and_forecast(records, reference_time_s=12.0)
    second = baseline.train_and_forecast(records, reference_time_s=12.0)
    assert first == second
    series = first.series[0]
    assert series.status is MLBaselineStatus.TRAINED
    assert series.model is not None
    assert len(series.model.coefficients) == 5
    assert len(series.forecasts) == 3
    assert series.forecasts[0].predicted_value == pytest.approx(8.0, abs=1e-5)
    assert series.forecasts[1].predicted_value == pytest.approx(7.0, abs=1e-5)
    assert series.model.metrics.mean_absolute_error == pytest.approx(0.0, abs=1e-5)
    assert len(series.model.model_fingerprint) == 64


def test_ml_baseline_uses_temporal_holdout() -> None:
    config = MLBaselineConfig(minimum_samples=8, test_fraction=0.25)
    result = MLPredictiveBaseline(config).train_and_forecast(
        history([10.0, 11.0, 13.0, 16.0, 20.0, 25.0, 31.0, 38.0, 46.0, 55.0, 65.0, 76.0]),
        reference_time_s=12.0,
    )
    metrics = result.series[0].model.metrics if result.series[0].model else None
    assert metrics is not None
    assert metrics.train_samples > metrics.test_samples
    assert metrics.test_samples >= 1


def test_ml_baseline_reports_insufficient_history() -> None:
    result = MLPredictiveBaseline(
        MLBaselineConfig(lag_steps=3, minimum_samples=10)
    ).train_and_forecast(history([1.0, 2.0, 3.0, 4.0, 5.0]), reference_time_s=5.0)
    assert result.series[0].status is MLBaselineStatus.INSUFFICIENT_HISTORY
    assert result.series[0].forecasts == []
    assert result.trained_count == 0


def test_ml_baseline_separates_metrics() -> None:
    sinr = history([20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0, 10.0, 9.0])
    capacity = [
        item.model_copy(
            update={
                "record_id": f"cap-{item.sequence}",
                "metric": TelemetryMetric.CAPACITY_BPS,
                "value": item.value * 1_000_000,
                "unit": "bit/s",
            }
        )
        for item in sinr
    ]
    result = MLPredictiveBaseline().train_and_forecast(sinr + capacity, reference_time_s=12.0)
    assert {(item.source_id, item.metric) for item in result.series} == {
        ("uav-a:ml-01", TelemetryMetric.SINR_DB),
        ("uav-a:ml-01", TelemetryMetric.CAPACITY_BPS),
    }
