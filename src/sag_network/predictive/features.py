from __future__ import annotations

from collections.abc import Iterable
from math import sqrt

from sag_network.predictive.models import PredictiveConfig, TelemetryFeatureVector
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _sample_variance(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    return sum((value - mean) ** 2 for value in values) / len(values)


def _linear_trend(points: list[tuple[float, float]]) -> tuple[float, float]:
    if len(points) < 2:
        return 0.0, 1.0
    t0 = points[0][0]
    x_values = [timestamp - t0 for timestamp, _ in points]
    y_values = [value for _, value in points]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    if denominator == 0.0:
        return 0.0, 1.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values)) / denominator
    residual_sum = sum((y - (y_mean + slope * (x - x_mean))) ** 2 for x, y in zip(x_values, y_values))
    total_sum = sum((y - y_mean) ** 2 for y in y_values)
    if total_sum == 0.0:
        return slope, 1.0
    r_squared = max(0.0, min(1.0, 1.0 - residual_sum / total_sum))
    return slope, r_squared


def extract_features(
    records: Iterable[TelemetryRecord],
    *,
    reference_time_s: float,
    config: PredictiveConfig | None = None,
) -> list[TelemetryFeatureVector]:
    """Build deterministic time-series features from accepted telemetry history."""
    effective_config = config or PredictiveConfig()
    grouped: dict[tuple[str, TelemetryMetric], list[TelemetryRecord]] = {}
    for record in records:
        grouped.setdefault((record.source_id, record.metric), []).append(record)

    features: list[TelemetryFeatureVector] = []
    for (source_id, metric), series in sorted(grouped.items(), key=lambda item: item[0]):
        ordered = sorted(series, key=lambda item: (item.timestamp_s, item.sequence))
        window = ordered[-effective_config.history_window :]
        latest = window[-1]
        values = [record.value for record in window]
        mean_value = sum(values) / len(values)
        trend_per_s, r_squared = _linear_trend(
            [(record.timestamp_s, record.value) for record in window]
        )
        if len(window) >= 2:
            previous = window[-2]
            elapsed = latest.timestamp_s - previous.timestamp_s
            last_delta = (latest.value - previous.value) / elapsed if elapsed > 0 else 0.0
        else:
            last_delta = 0.0
        age_s = max(0.0, reference_time_s - latest.timestamp_s)
        features.append(
            TelemetryFeatureVector(
                source_id=source_id,
                domain=latest.domain,
                metric=metric,
                sample_count=len(window),
                latest_value=latest.value,
                latest_timestamp_s=latest.timestamp_s,
                age_s=age_s,
                stale=age_s > effective_config.max_input_age_s,
                mean_value=mean_value,
                standard_deviation=sqrt(_sample_variance(values, mean_value)),
                minimum_value=min(values),
                maximum_value=max(values),
                trend_per_s=trend_per_s,
                last_delta_per_s=last_delta,
                trend_r_squared=r_squared,
            )
        )
    return features
