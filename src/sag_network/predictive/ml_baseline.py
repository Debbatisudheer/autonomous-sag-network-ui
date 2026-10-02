from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable

from sag_network.predictive.ml_models import (
    MLBaselineConfig,
    MLBaselineForecast,
    MLBaselineMetrics,
    MLBaselineModel,
    MLBaselineReport,
    MLBaselineSeries,
    MLBaselineStatus,
)
from sag_network.telemetry.models import TelemetryRecord


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small dense system deterministically with partial pivoting."""
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular regression system")
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for current in range(column + 1, size):
            factor = augmented[current][column] / pivot_value
            if factor == 0.0:
                continue
            for index in range(column, size + 1):
                augmented[current][index] -= factor * augmented[column][index]
    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        remainder = augmented[row][size] - sum(
            augmented[row][column] * solution[column] for column in range(row + 1, size)
        )
        solution[row] = remainder / augmented[row][row]
    return solution


def _features(history: list[float], lag_steps: int) -> list[float]:
    if len(history) < lag_steps:
        raise ValueError("not enough history for configured lags")
    recent = history[-lag_steps:]
    lags = list(reversed(recent))
    delta = recent[-1] - recent[-2]
    return [*lags, delta, sum(recent) / len(recent)]


def _training_samples(values: list[float], lag_steps: int) -> tuple[list[list[float]], list[float]]:
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(lag_steps, len(values)):
        history = values[index - lag_steps : index]
        features.append(_features(history, lag_steps))
        targets.append(values[index])
    return features, targets


def _fit_ridge(features: list[list[float]], targets: list[float], alpha: float) -> tuple[float, ...]:
    dimension = len(features[0])
    matrix = [[0.0 for _ in range(dimension + 1)] for _ in range(dimension + 1)]
    vector = [0.0 for _ in range(dimension + 1)]
    for row, target in zip(features, targets):
        augmented = [1.0, *row]
        for i in range(dimension + 1):
            vector[i] += augmented[i] * target
            for j in range(dimension + 1):
                matrix[i][j] += augmented[i] * augmented[j]
    for index in range(1, dimension + 1):
        matrix[index][index] += alpha
    return tuple(_solve_linear_system(matrix, vector))


def _predict(coefficients: tuple[float, ...], values: list[float], lag_steps: int) -> float:
    row = _features(values, lag_steps)
    return coefficients[0] + sum(coefficient * value for coefficient, value in zip(coefficients[1:], row))


def _metrics(
    targets: list[float], predictions: list[float], *, train_samples: int
) -> MLBaselineMetrics:
    errors = [prediction - target for target, prediction in zip(targets, predictions)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean_target = sum(targets) / len(targets)
    total = sum((target - mean_target) ** 2 for target in targets)
    residual = sum(error * error for error in errors)
    r_squared = 1.0 if total == 0.0 and residual == 0.0 else (0.0 if total == 0.0 else 1.0 - residual / total)
    return MLBaselineMetrics(
        train_samples=train_samples,
        test_samples=len(targets),
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        r_squared=r_squared,
    )


def _confidence(metrics: MLBaselineMetrics, training_samples: int) -> float:
    validation_score = max(0.0, min(1.0, metrics.r_squared))
    sample_score = min(1.0, training_samples / 50.0)
    return max(0.0, min(1.0, 0.5 * validation_score + 0.5 * sample_score))


class MLPredictiveBaseline:
    """Deterministic supervised ML baseline trained from historical telemetry."""

    def __init__(self, config: MLBaselineConfig | None = None) -> None:
        self.config = config or MLBaselineConfig()

    def train_and_forecast(
        self,
        records: Iterable[TelemetryRecord],
        *,
        reference_time_s: float,
    ) -> MLBaselineReport:
        grouped: dict[tuple[str, str], list[TelemetryRecord]] = {}
        for record in records:
            grouped.setdefault((record.source_id, record.metric.value), []).append(record)
        series_results: list[MLBaselineSeries] = []
        for key in sorted(grouped):
            ordered = sorted(grouped[key], key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
            series_results.append(self._fit_series(ordered, reference_time_s=reference_time_s))
        return MLBaselineReport(timestamp_s=reference_time_s, config=self.config, series=series_results)

    def _fit_series(self, records: list[TelemetryRecord], *, reference_time_s: float) -> MLBaselineSeries:
        latest = records[-1]
        values = [record.value for record in records]
        features, targets = _training_samples(values, self.config.lag_steps)
        if len(targets) < self.config.minimum_samples:
            return MLBaselineSeries(
                source_id=latest.source_id,
                domain=latest.domain,
                metric=latest.metric,
                status=MLBaselineStatus.INSUFFICIENT_HISTORY,
                reason="telemetry history does not contain the configured minimum supervised samples",
            )
        test_size = max(1, math.ceil(len(targets) * self.config.test_fraction))
        train_size = len(targets) - test_size
        train_features = features[:train_size]
        train_targets = targets[:train_size]
        test_features = features[train_size:]
        test_targets = targets[train_size:]
        coefficients = _fit_ridge(train_features, train_targets, self.config.ridge_alpha)
        test_predictions = [
            coefficients[0] + sum(coefficient * value for coefficient, value in zip(coefficients[1:], row))
            for row in test_features
        ]
        metric_result = _metrics(test_targets, test_predictions, train_samples=train_size)
        feature_names = tuple(
            [f"lag_{index}" for index in range(1, self.config.lag_steps + 1)]
            + ["delta_1", "rolling_mean"]
        )
        model_payload = {
            "source_id": latest.source_id,
            "domain": latest.domain.value,
            "metric": latest.metric.value,
            "lag_steps": self.config.lag_steps,
            "feature_names": feature_names,
            "coefficients": coefficients,
            "ridge_alpha": self.config.ridge_alpha,
            "training_samples": train_size,
            "metrics": metric_result.model_dump(mode="json"),
        }
        model = MLBaselineModel(
            source_id=latest.source_id,
            domain=latest.domain,
            metric=latest.metric,
            lag_steps=self.config.lag_steps,
            feature_names=feature_names,
            coefficients=coefficients[1:],
            intercept=coefficients[0],
            ridge_alpha=self.config.ridge_alpha,
            training_samples=train_size,
            metrics=metric_result,
            model_fingerprint=_fingerprint(model_payload),
        )
        history = values[:]
        confidence = _confidence(metric_result, train_size)
        forecasts: list[MLBaselineForecast] = []
        for step in range(1, self.config.horizon_steps + 1):
            predicted = _predict(coefficients, history, self.config.lag_steps)
            timestamp = reference_time_s + step * self.config.step_s
            forecasts.append(
                MLBaselineForecast(
                    source_id=latest.source_id,
                    domain=latest.domain,
                    metric=latest.metric,
                    status=MLBaselineStatus.TRAINED,
                    forecast_timestamp_s=timestamp,
                    horizon_s=step * self.config.step_s,
                    predicted_value=predicted,
                    confidence_score=confidence,
                    model_fingerprint=model.model_fingerprint,
                )
            )
            history.append(predicted)
        return MLBaselineSeries(
            source_id=latest.source_id,
            domain=latest.domain,
            metric=latest.metric,
            status=MLBaselineStatus.TRAINED,
            model=model,
            forecasts=forecasts,
        )
