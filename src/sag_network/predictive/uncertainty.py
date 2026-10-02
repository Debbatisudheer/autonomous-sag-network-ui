from __future__ import annotations

import math
from collections.abc import Iterable

from sag_network.predictive.deep_learning_models import DeepLearningConfig, DeepLearningModel
from sag_network.predictive.time_series_deep_learning import (
    _predict,
    _windows,
    TimeSeriesDeepLearning,
)
from sag_network.predictive.uncertainty_models import (
    UncertaintyConfig,
    UncertaintyInterval,
    UncertaintyReport,
    UncertaintySeries,
    UncertaintyStatus,
)
from sag_network.telemetry.models import TelemetryRecord


def _finite_residuals(values: list[float]) -> list[float]:
    return sorted(abs(value) for value in values if math.isfinite(value))


def _conformal_quantile(residuals: list[float], confidence_level: float) -> float:
    if not residuals:
        return 0.0
    count = len(residuals)
    rank = math.ceil((count + 1) * confidence_level)
    index = min(count, max(1, rank)) - 1
    return residuals[index]


def _temporal_calibration_residuals(
    values: list[float],
    model: DeepLearningModel,
    deep_learning_config: DeepLearningConfig,
) -> list[float]:
    features, targets = _windows(values, deep_learning_config.lag_steps)
    test_size = max(1, math.ceil(len(targets) * deep_learning_config.test_fraction))
    train_size = len(targets) - test_size
    if train_size < 1:
        return []
    model_features = features[train_size:]
    model_targets = targets[train_size:]
    residuals: list[float] = []
    for row, target in zip(model_features, model_targets):
        prediction = _predict(
            row,
            model.lag_steps,
            model.input_mean,
            model.input_scale,
            model.target_mean,
            model.target_scale,
            [list(item) for item in model.hidden_weights],
            list(model.hidden_bias),
            list(model.output_weights),
            model.output_bias,
        )
        residuals.append(prediction - target)
    return _finite_residuals(residuals)


def _uncertainty_score(interval_width: float, point_value: float) -> float:
    relative = interval_width / max(abs(point_value), 1e-9)
    return max(0.0, min(1.0, relative / 2.0))


class UncertaintyAwarePrediction:
    """Calibrate Phase 33 forecasts with deterministic holdout residual intervals."""

    def __init__(
        self,
        uncertainty_config: UncertaintyConfig | None = None,
        deep_learning_config: DeepLearningConfig | None = None,
    ) -> None:
        self.uncertainty_config = uncertainty_config or UncertaintyConfig()
        self.deep_learning_config = deep_learning_config or DeepLearningConfig()
        self.deep_learning = TimeSeriesDeepLearning(self.deep_learning_config)

    def predict(
        self, records: Iterable[TelemetryRecord], *, reference_time_s: float
    ) -> UncertaintyReport:
        grouped: dict[tuple[str, str], list[TelemetryRecord]] = {}
        for record in records:
            grouped.setdefault((record.source_id, record.metric.value), []).append(record)
        results: list[UncertaintySeries] = []
        for key in sorted(grouped):
            ordered = sorted(
                grouped[key],
                key=lambda item: (item.timestamp_s, item.sequence, item.record_id),
            )
            results.append(self._calibrate_series(ordered, reference_time_s=reference_time_s))
        return UncertaintyReport(
            timestamp_s=reference_time_s,
            config=self.uncertainty_config,
            series=results,
        )

    def _calibrate_series(
        self, records: list[TelemetryRecord], *, reference_time_s: float
    ) -> UncertaintySeries:
        latest = records[-1]
        values = [record.value for record in records]
        base_report = self.deep_learning.train_and_forecast(records, reference_time_s=reference_time_s)
        base_series = base_report.series[0]
        if base_series.model is None:
            return UncertaintySeries(
                source_id=latest.source_id,
                domain=latest.domain,
                metric=latest.metric,
                status=UncertaintyStatus.INSUFFICIENT_HISTORY,
                calibration_samples=0,
                reason=base_series.reason,
            )
        residuals = _temporal_calibration_residuals(values, base_series.model, self.deep_learning_config)
        if len(residuals) < self.uncertainty_config.minimum_calibration_samples:
            return UncertaintySeries(
                source_id=latest.source_id,
                domain=latest.domain,
                metric=latest.metric,
                status=UncertaintyStatus.INSUFFICIENT_CALIBRATION,
                calibration_samples=len(residuals),
                reason="temporal holdout does not contain enough calibration residuals",
            )
        quantile = _conformal_quantile(residuals, self.uncertainty_config.confidence_level)
        intervals: list[UncertaintyInterval] = []
        for forecast in base_series.forecasts:
            horizon_delta = max(0.0, forecast.horizon_s - self.deep_learning_config.step_s)
            growth = 1.0 + (
                self.uncertainty_config.horizon_growth
                * horizon_delta
                / self.deep_learning_config.step_s
            )
            margin = quantile * growth
            predicted = forecast.predicted_value
            if predicted is None:
                continue
            width = 2.0 * margin
            intervals.append(
                UncertaintyInterval(
                    source_id=forecast.source_id,
                    domain=forecast.domain,
                    metric=forecast.metric,
                    forecast_timestamp_s=forecast.forecast_timestamp_s,
                    horizon_s=forecast.horizon_s,
                    predicted_value=predicted,
                    lower_bound=predicted - margin,
                    upper_bound=predicted + margin,
                    interval_width=width,
                    confidence_level=self.uncertainty_config.confidence_level,
                    uncertainty_score=_uncertainty_score(width, predicted),
                    calibration_residual_quantile=quantile,
                    model_fingerprint=base_series.model.model_fingerprint,
                )
            )
        return UncertaintySeries(
            source_id=latest.source_id,
            domain=latest.domain,
            metric=latest.metric,
            status=UncertaintyStatus.CALIBRATED,
            calibration_samples=len(residuals),
            calibration_quantile=quantile,
            intervals=intervals,
        )
