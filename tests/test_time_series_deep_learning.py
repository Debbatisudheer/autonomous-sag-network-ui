from __future__ import annotations

from sag_network.domain.unified import NetworkDomain
from sag_network.predictive.deep_learning_models import DeepLearningConfig, DeepLearningStatus
from sag_network.predictive.time_series_deep_learning import TimeSeriesDeepLearning
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def history(values: list[float]) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"dl-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:dl-01",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=value,
            unit="dB",
        )
        for index, value in enumerate(values, start=1)
    ]


def test_deep_learning_is_deterministic_and_forecasts() -> None:
    config = DeepLearningConfig(lag_steps=5, minimum_samples=12, hidden_units=6, epochs=80)
    records = history([30.0, 29.5, 29.0, 28.5, 28.0, 27.5, 27.0, 26.5, 26.0, 25.5, 25.0, 24.5, 24.0, 23.5, 23.0, 22.5, 22.0, 21.5, 21.0, 20.5, 20.0, 19.5, 19.0, 18.5, 18.0])
    first = TimeSeriesDeepLearning(config).train_and_forecast(records, reference_time_s=25.0)
    second = TimeSeriesDeepLearning(config).train_and_forecast(records, reference_time_s=25.0)
    assert first == second
    series = first.series[0]
    assert series.status is DeepLearningStatus.TRAINED
    assert series.model is not None
    assert series.model.hidden_units == 6
    assert len(series.forecasts) == 3
    assert len(series.model.model_fingerprint) == 64


def test_deep_learning_uses_temporal_holdout() -> None:
    config = DeepLearningConfig(lag_steps=4, minimum_samples=10, hidden_units=4, epochs=40)
    result = TimeSeriesDeepLearning(config).train_and_forecast(
        history([10.0, 11.0, 13.0, 16.0, 20.0, 25.0, 31.0, 38.0, 46.0, 55.0, 65.0, 76.0, 88.0, 101.0, 115.0]),
        reference_time_s=15.0,
    )
    model = result.series[0].model
    assert model is not None
    assert model.training_samples > model.metrics.test_samples
    assert model.metrics.test_samples >= 1


def test_deep_learning_reports_insufficient_history() -> None:
    result = TimeSeriesDeepLearning(
        DeepLearningConfig(lag_steps=4, minimum_samples=12, epochs=20)
    ).train_and_forecast(history([1.0, 2.0, 3.0, 4.0, 5.0]), reference_time_s=5.0)
    assert result.series[0].status is DeepLearningStatus.INSUFFICIENT_HISTORY
    assert result.series[0].forecasts == []
    assert result.trained_count == 0


def test_deep_learning_separates_metrics() -> None:
    sinr = history([20.0 + index * 0.1 for index in range(25)])
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
    result = TimeSeriesDeepLearning(
        DeepLearningConfig(lag_steps=5, minimum_samples=10, hidden_units=4, epochs=30)
    ).train_and_forecast(sinr + capacity, reference_time_s=25.0)
    assert {(item.source_id, item.metric) for item in result.series} == {
        ("uav-a:dl-01", TelemetryMetric.SINR_DB),
        ("uav-a:dl-01", TelemetryMetric.CAPACITY_BPS),
    }
