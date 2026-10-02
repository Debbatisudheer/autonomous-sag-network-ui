from __future__ import annotations

from collections.abc import Iterable

from sag_network.predictive.features import extract_features
from sag_network.predictive.models import (
    ForecastMethod,
    ForecastPoint,
    ForecastSeries,
    PredictionStatus,
    PredictiveConfig,
)
from sag_network.telemetry.models import TelemetryRecord


def _linear_fit(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    t0 = points[0][0]
    x_values = [timestamp - t0 for timestamp, _ in points]
    y_values = [value for _, value in points]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    if denominator == 0.0:
        return y_mean, 0.0, 1.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values)) / denominator
    intercept = y_mean - slope * x_mean
    residual_sum = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(x_values, y_values))
    total_sum = sum((y - y_mean) ** 2 for y in y_values)
    r_squared = 1.0 if total_sum == 0.0 else max(0.0, min(1.0, 1.0 - residual_sum / total_sum))
    return intercept, slope, r_squared


def _confidence(sample_count: int, r_squared: float) -> float:
    sample_factor = min(1.0, sample_count / 10.0)
    return max(0.0, min(1.0, 0.5 * sample_factor + 0.5 * r_squared))


def forecast_history(
    records: Iterable[TelemetryRecord],
    *,
    reference_time_s: float,
    config: PredictiveConfig | None = None,
) -> list[ForecastSeries]:
    """Generate deterministic future forecasts from accepted telemetry history."""
    effective_config = config or PredictiveConfig()
    grouped: dict[tuple[str, str], list[TelemetryRecord]] = {}
    for record in records:
        grouped.setdefault((record.source_id, record.metric.value), []).append(record)

    features = extract_features(records, reference_time_s=reference_time_s, config=effective_config)
    feature_map = {(item.source_id, item.metric.value): item for item in features}
    series_results: list[ForecastSeries] = []

    for key in sorted(grouped):
        source_id, _metric_value = key
        feature = feature_map[key]
        series = sorted(grouped[key], key=lambda item: (item.timestamp_s, item.sequence))
        window = series[-effective_config.history_window :]
        method = effective_config.method
        status = PredictionStatus.READY
        reason: str | None = None

        if feature.stale and effective_config.reject_stale_inputs:
            status = PredictionStatus.STALE_INPUT
            reason = "latest telemetry sample exceeds configured prediction age"
        elif len(window) < effective_config.min_points:
            status = PredictionStatus.INSUFFICIENT_HISTORY
            reason = "telemetry history does not contain the configured minimum sample count"

        if status is not PredictionStatus.READY:
            series_results.append(
                ForecastSeries(
                    source_id=source_id,
                    domain=feature.domain,
                    metric=feature.metric,
                    status=status,
                    method=method,
                    feature_vector=feature,
                    points=[],
                    reason=reason,
                )
            )
            continue

        points = [(record.timestamp_s, record.value) for record in window]
        intercept, slope, r_squared = _linear_fit(points)
        confidence = _confidence(len(window), r_squared)
        last_timestamp = window[-1].timestamp_s
        future_points: list[ForecastPoint] = []
        for step in range(1, effective_config.horizon_steps + 1):
            forecast_timestamp = reference_time_s + step * effective_config.step_s
            if method is ForecastMethod.LAST_VALUE:
                predicted = feature.latest_value
                point_confidence = min(confidence, 0.6)
            else:
                x = forecast_timestamp - points[0][0]
                predicted = intercept + slope * x
                point_confidence = confidence
            future_points.append(
                ForecastPoint(
                    source_id=source_id,
                    domain=feature.domain,
                    metric=feature.metric,
                    forecast_timestamp_s=forecast_timestamp,
                    horizon_s=max(0.0, forecast_timestamp - reference_time_s),
                    predicted_value=predicted,
                    confidence_score=point_confidence,
                    method=method,
                    input_sample_count=len(window),
                    source_timestamp_s=last_timestamp,
                )
            )
        series_results.append(
            ForecastSeries(
                source_id=source_id,
                domain=feature.domain,
                metric=feature.metric,
                status=status,
                method=method,
                feature_vector=feature.model_copy(update={"trend_r_squared": r_squared}),
                points=future_points,
                reason=None,
            )
        )
    return series_results
