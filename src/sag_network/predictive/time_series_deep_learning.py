from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Iterable

from sag_network.predictive.deep_learning_models import (
    DeepLearningConfig,
    DeepLearningForecast,
    DeepLearningMetrics,
    DeepLearningModel,
    DeepLearningReport,
    DeepLearningSeries,
    DeepLearningStatus,
)
from sag_network.telemetry.models import TelemetryRecord


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _windows(values: list[float], lag_steps: int) -> tuple[list[list[float]], list[float]]:
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(lag_steps, len(values)):
        features.append(values[index - lag_steps : index])
        targets.append(values[index])
    return features, targets


def _mean_scale(rows: list[list[float]]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    width = len(rows[0])
    means = tuple(sum(row[index] for row in rows) / len(rows) for index in range(width))
    scales = tuple(
        max(
            math.sqrt(sum((row[index] - means[index]) ** 2 for row in rows) / len(rows)),
            1e-9,
        )
        for index in range(width)
    )
    return means, scales


def _standardize(rows: list[list[float]], means: tuple[float, ...], scales: tuple[float, ...]) -> list[list[float]]:
    return [[(value - mean) / scale for value, mean, scale in zip(row, means, scales)] for row in rows]


def _tanh_derivative(value: float) -> float:
    return 1.0 - value * value


def _forward(
    row: list[float], hidden_weights: list[list[float]], hidden_bias: list[float], output_weights: list[float], output_bias: float
) -> tuple[list[float], float]:
    hidden = []
    for weights, bias in zip(hidden_weights, hidden_bias):
        activation = math.tanh(sum(weight * value for weight, value in zip(weights, row)) + bias)
        hidden.append(activation)
    output = output_bias + sum(weight * value for weight, value in zip(output_weights, hidden))
    return hidden, output


def _train_network(
    features: list[list[float]],
    targets: list[float],
    config: DeepLearningConfig,
) -> tuple[list[list[float]], list[float], list[float], float, float]:
    input_width = len(features[0])
    rng = random.Random(config.seed)
    hidden_weights = [
        [rng.uniform(-0.15, 0.15) for _ in range(input_width)]
        for _ in range(config.hidden_units)
    ]
    hidden_bias = [0.0 for _ in range(config.hidden_units)]
    output_weights = [rng.uniform(-0.15, 0.15) for _ in range(config.hidden_units)]
    output_bias = 0.0
    target_mean = sum(targets) / len(targets)
    target_scale = max(math.sqrt(sum((value - target_mean) ** 2 for value in targets) / len(targets)), 1e-9)
    normalized_targets = [(value - target_mean) / target_scale for value in targets]
    for _ in range(config.epochs):
        gradient_hidden = [[0.0 for _ in range(input_width)] for _ in range(config.hidden_units)]
        gradient_hidden_bias = [0.0 for _ in range(config.hidden_units)]
        gradient_output = [0.0 for _ in range(config.hidden_units)]
        gradient_output_bias = 0.0
        for row, target in zip(features, normalized_targets):
            hidden, prediction = _forward(
                row, hidden_weights, hidden_bias, output_weights, output_bias
            )
            error = prediction - target
            gradient_output_bias += error
            for hidden_index, hidden_value in enumerate(hidden):
                gradient_output[hidden_index] += error * hidden_value
                hidden_error = error * output_weights[hidden_index] * _tanh_derivative(hidden_value)
                gradient_hidden_bias[hidden_index] += hidden_error
                for input_index, input_value in enumerate(row):
                    gradient_hidden[hidden_index][input_index] += hidden_error * input_value
        scale = 2.0 / len(features)
        for hidden_index in range(config.hidden_units):
            for input_index in range(input_width):
                hidden_weights[hidden_index][input_index] -= (
                    config.learning_rate * scale * gradient_hidden[hidden_index][input_index]
                )
            hidden_bias[hidden_index] -= config.learning_rate * scale * gradient_hidden_bias[hidden_index]
            output_weights[hidden_index] -= config.learning_rate * scale * gradient_output[hidden_index]
        output_bias -= config.learning_rate * scale * gradient_output_bias
    return hidden_weights, hidden_bias, output_weights, output_bias, target_scale


def _predict(
    values: list[float],
    lag_steps: int,
    input_mean: tuple[float, ...],
    input_scale: tuple[float, ...],
    target_mean: float,
    target_scale: float,
    hidden_weights: list[list[float]],
    hidden_bias: list[float],
    output_weights: list[float],
    output_bias: float,
) -> float:
    raw = values[-lag_steps:]
    row = [(value - mean) / scale for value, mean, scale in zip(raw, input_mean, input_scale)]
    _, prediction = _forward(row, hidden_weights, hidden_bias, output_weights, output_bias)
    return target_mean + target_scale * prediction


def _metrics(targets: list[float], predictions: list[float], train_samples: int, train_loss: float) -> DeepLearningMetrics:
    errors = [prediction - target for target, prediction in zip(targets, predictions)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean_target = sum(targets) / len(targets)
    total = sum((target - mean_target) ** 2 for target in targets)
    residual = sum(error * error for error in errors)
    r_squared = 1.0 if total == 0.0 and residual == 0.0 else (0.0 if total == 0.0 else 1.0 - residual / total)
    return DeepLearningMetrics(
        train_samples=train_samples,
        test_samples=len(targets),
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        r_squared=r_squared,
        train_loss=train_loss,
    )


def _confidence(metrics: DeepLearningMetrics, training_samples: int) -> float:
    validation_score = max(0.0, min(1.0, metrics.r_squared))
    sample_score = min(1.0, training_samples / 100.0)
    return max(0.0, min(1.0, 0.5 * validation_score + 0.5 * sample_score))


class TimeSeriesDeepLearning:
    """Deterministic sequence-to-one neural network for telemetry forecasting."""

    def __init__(self, config: DeepLearningConfig | None = None) -> None:
        self.config = config or DeepLearningConfig()

    def train_and_forecast(
        self, records: Iterable[TelemetryRecord], *, reference_time_s: float
    ) -> DeepLearningReport:
        grouped: dict[tuple[str, str], list[TelemetryRecord]] = {}
        for record in records:
            grouped.setdefault((record.source_id, record.metric.value), []).append(record)
        series_results: list[DeepLearningSeries] = []
        for key in sorted(grouped):
            ordered = sorted(grouped[key], key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
            series_results.append(self._fit_series(ordered, reference_time_s=reference_time_s))
        return DeepLearningReport(timestamp_s=reference_time_s, config=self.config, series=series_results)

    def _fit_series(self, records: list[TelemetryRecord], *, reference_time_s: float) -> DeepLearningSeries:
        latest = records[-1]
        values = [record.value for record in records]
        features, targets = _windows(values, self.config.lag_steps)
        if len(targets) < self.config.minimum_samples:
            return DeepLearningSeries(
                source_id=latest.source_id,
                domain=latest.domain,
                metric=latest.metric,
                status=DeepLearningStatus.INSUFFICIENT_HISTORY,
                reason="telemetry history does not contain the configured minimum supervised samples",
            )
        test_size = max(1, math.ceil(len(targets) * self.config.test_fraction))
        train_size = len(targets) - test_size
        train_features = features[:train_size]
        train_targets = targets[:train_size]
        test_features = features[train_size:]
        test_targets = targets[train_size:]
        input_mean, input_scale = _mean_scale(train_features)
        normalized_train_features = _standardize(train_features, input_mean, input_scale)
        hidden_weights, hidden_bias, output_weights, output_bias, target_scale = _train_network(
            normalized_train_features, train_targets, self.config
        )
        target_mean = sum(train_targets) / len(train_targets)
        train_predictions = [
            _predict(
                row,
                self.config.lag_steps,
                input_mean,
                input_scale,
                target_mean,
                target_scale,
                hidden_weights,
                hidden_bias,
                output_weights,
                output_bias,
            )
            for row in train_features
        ]
        test_predictions = [
            _predict(
                row,
                self.config.lag_steps,
                input_mean,
                input_scale,
                target_mean,
                target_scale,
                hidden_weights,
                hidden_bias,
                output_weights,
                output_bias,
            )
            for row in test_features
        ]
        train_loss = sum((prediction - target) ** 2 for prediction, target in zip(train_predictions, train_targets)) / len(train_targets)
        metrics = _metrics(test_targets, test_predictions, train_size, train_loss)
        model_payload = {
            "source_id": latest.source_id,
            "domain": latest.domain.value,
            "metric": latest.metric.value,
            "lag_steps": self.config.lag_steps,
            "hidden_units": self.config.hidden_units,
            "input_mean": input_mean,
            "input_scale": input_scale,
            "target_mean": target_mean,
            "target_scale": target_scale,
            "hidden_weights": hidden_weights,
            "hidden_bias": hidden_bias,
            "output_weights": output_weights,
            "output_bias": output_bias,
            "epochs": self.config.epochs,
            "learning_rate": self.config.learning_rate,
            "seed": self.config.seed,
            "training_samples": train_size,
        }
        model = DeepLearningModel(
            source_id=latest.source_id,
            domain=latest.domain,
            metric=latest.metric,
            lag_steps=self.config.lag_steps,
            hidden_units=self.config.hidden_units,
            input_mean=input_mean,
            input_scale=input_scale,
            target_mean=target_mean,
            target_scale=target_scale,
            hidden_weights=tuple(tuple(row) for row in hidden_weights),
            hidden_bias=tuple(hidden_bias),
            output_weights=tuple(output_weights),
            output_bias=output_bias,
            training_samples=train_size,
            epochs=self.config.epochs,
            learning_rate=self.config.learning_rate,
            metrics=metrics,
            model_fingerprint=_fingerprint(model_payload),
        )
        history = values[:]
        confidence = _confidence(metrics, train_size)
        forecasts: list[DeepLearningForecast] = []
        for step in range(1, self.config.horizon_steps + 1):
            predicted = _predict(
                history,
                self.config.lag_steps,
                input_mean,
                input_scale,
                target_mean,
                target_scale,
                hidden_weights,
                hidden_bias,
                output_weights,
                output_bias,
            )
            forecasts.append(
                DeepLearningForecast(
                    source_id=latest.source_id,
                    domain=latest.domain,
                    metric=latest.metric,
                    status=DeepLearningStatus.TRAINED,
                    forecast_timestamp_s=reference_time_s + step * self.config.step_s,
                    horizon_s=step * self.config.step_s,
                    predicted_value=predicted,
                    confidence_score=confidence,
                    model_fingerprint=model.model_fingerprint,
                )
            )
            history.append(predicted)
        return DeepLearningSeries(
            source_id=latest.source_id,
            domain=latest.domain,
            metric=latest.metric,
            status=DeepLearningStatus.TRAINED,
            model=model,
            forecasts=forecasts,
        )
