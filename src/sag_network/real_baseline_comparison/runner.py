from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sag_network.real_baseline_comparison.models import (
    RealBaselineComparisonConfig,
    RealBaselineComparisonReport,
    RealBaselineMetric,
    RealBaselineMethod,
    RealSeriesComparison,
)


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_timestamp(value: str) -> float:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        parsed = datetime.fromisoformat(stripped)
        if parsed.tzinfo is None:
            raise ValueError("ISO-8601 timestamp must include timezone information")
        return parsed.timestamp()


def _fit_ridge(
    features: list[list[float]],
    targets: list[float],
    alpha: float,
) -> tuple[float, ...]:
    dimension = len(features[0])
    size = dimension + 1
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    vector = [0.0 for _ in range(size)]
    for feature_row, target in zip(features, targets, strict=True):
        augmented = [1.0, *feature_row]
        for feature_index in range(size):
            vector[feature_index] += augmented[feature_index] * target
            for matrix_index in range(size):
                matrix[feature_index][matrix_index] += (
                    augmented[feature_index] * augmented[matrix_index]
                )
    for regularized_index in range(1, size):
        matrix[regularized_index][regularized_index] += alpha
    for pivot_column in range(size):
        pivot_row = max(
            range(pivot_column, size),
            key=lambda candidate: abs(matrix[candidate][pivot_column]),
        )
        if abs(matrix[pivot_row][pivot_column]) < 1e-12:
            raise ValueError("singular regression system")
        if pivot_row != pivot_column:
            matrix[pivot_column], matrix[pivot_row] = matrix[pivot_row], matrix[pivot_column]
            vector[pivot_column], vector[pivot_row] = vector[pivot_row], vector[pivot_column]
        pivot_value = matrix[pivot_column][pivot_column]
        for elimination_row in range(pivot_column + 1, size):
            factor = matrix[elimination_row][pivot_column] / pivot_value
            for elimination_column in range(pivot_column, size):
                matrix[elimination_row][elimination_column] -= (
                    factor * matrix[pivot_column][elimination_column]
                )
            vector[elimination_row] -= factor * vector[pivot_column]
    solution = [0.0] * size
    for solution_row in range(size - 1, -1, -1):
        remainder = vector[solution_row] - sum(
            matrix[solution_row][solution_column] * solution[solution_column]
            for solution_column in range(solution_row + 1, size)
        )
        solution[solution_row] = remainder / matrix[solution_row][solution_row]
    return tuple(solution)


def _fit_and_predict(
    source_id: str,
    values: list[float],
    config: RealBaselineComparisonConfig,
) -> tuple[tuple[float, ...], tuple[float, ...], str]:
    lag = config.lag_steps
    features = [
        [
            *reversed(values[index - lag : index]),
            values[index - 1] - values[index - 2],
            sum(values[index - lag : index]) / lag,
        ]
        for index in range(lag, len(values))
    ]
    targets = values[lag:]
    test_size = max(1, math.ceil(len(targets) * config.test_fraction))
    train_size = len(targets) - test_size
    train_features = features[:train_size]
    train_targets = targets[:train_size]
    means = [
        sum(row[index] for row in train_features) / train_size
        for index in range(len(train_features[0]))
    ]
    scales = [
        math.sqrt(
            sum((row[index] - means[index]) ** 2 for row in train_features)
            / train_size
        )
        for index in range(len(means))
    ]
    scales = [scale if scale > 1e-12 else 1.0 for scale in scales]
    target_mean = sum(train_targets) / train_size
    target_scale = math.sqrt(
        sum((value - target_mean) ** 2 for value in train_targets)
        / train_size
    )
    target_scale = target_scale if target_scale > 1e-12 else 1.0
    normalized_train = [
        [
            (value - mean) / scale
            for value, mean, scale in zip(row, means, scales, strict=True)
        ]
        for row in train_features
    ]
    normalized_targets = [(value - target_mean) / target_scale for value in train_targets]
    coefficients = _fit_ridge(normalized_train, normalized_targets, config.ridge_alpha)
    normalized_test = [
        [
            (value - mean) / scale
            for value, mean, scale in zip(row, means, scales, strict=True)
        ]
        for row in features[train_size:]
    ]
    predictions = tuple(
        target_mean
        + target_scale
        * (
            coefficients[0]
            + sum(
                coefficient * value
                for coefficient, value in zip(
                    coefficients[1:], row, strict=True
                )
            )
        )
        for row in normalized_test
    )
    actuals = tuple(targets[train_size:])
    errors = [prediction - actual for prediction, actual in zip(predictions, actuals, strict=True)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean_target = sum(actuals) / len(actuals)
    total = sum((target - mean_target) ** 2 for target in actuals)
    residual = sum(error * error for error in errors)
    r_squared = (
        1.0
        if total == 0.0 and residual == 0.0
        else (0.0 if total == 0.0 else 1.0 - residual / total)
    )
    model_payload = {
        "source_id": source_id,
        "lag_steps": config.lag_steps,
        "coefficients": coefficients,
        "feature_means": means,
        "feature_scales": scales,
        "target_mean": target_mean,
        "target_scale": target_scale,
        "training_samples": train_size,
        "mae": mae,
        "rmse": rmse,
        "r_squared": r_squared,
    }
    return predictions, actuals, _fingerprint(model_payload)


def _metrics(
    method: RealBaselineMethod,
    actuals: tuple[float, ...],
    predictions: tuple[float, ...],
) -> RealBaselineMetric:
    errors = [prediction - actual for prediction, actual in zip(predictions, actuals, strict=True)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean_actual = sum(actuals) / len(actuals)
    total = sum((actual - mean_actual) ** 2 for actual in actuals)
    residual = sum(error * error for error in errors)
    r_squared = (
        1.0
        if total == 0.0 and residual == 0.0
        else (0.0 if total == 0.0 else 1.0 - residual / total)
    )
    return RealBaselineMetric(
        method=method,
        sample_count=len(actuals),
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        r_squared=r_squared,
    )


class RealDataBaselineComparisonRunner:
    """Compare Phase 61's deterministic ridge forecast with simple real-data baselines."""

    def run(
        self,
        path: Path,
        *,
        config: RealBaselineComparisonConfig | None = None,
    ) -> RealBaselineComparisonReport:
        effective = config or RealBaselineComparisonConfig()
        if not path.is_file():
            raise FileNotFoundError(f"dataset does not exist: {path}")
        source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path = path.with_suffix(path.suffix + ".manifest.json")
        provenance_verified = False
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("sha256") != source_sha256:
                raise ValueError("provenance manifest SHA-256 does not match the dataset")
            provenance_verified = manifest.get("verified") is True
        if not provenance_verified:
            raise ValueError(
                "real-data baseline comparison requires a verified provenance manifest"
            )
        grouped: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
        row_count = 0
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"timestamp", "channel", "value"}
            if not required.issubset(set(reader.fieldnames or ())):
                raise ValueError("dataset must contain timestamp, channel, and value columns")
            for row in reader:
                row_count += 1
                try:
                    timestamp = _parse_timestamp(row["timestamp"])
                    value = float(row["value"])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"non-numeric timestamp/value at row {row_count + 1}") from exc
                if not math.isfinite(timestamp) or not math.isfinite(value):
                    continue
                train_flag = int(float(row.get("train", "1") or "1"))
                if train_flag == 1:
                    grouped[row["channel"].strip() or "opssat"].append(
                        (timestamp, value, row_count)
                    )
        series_results: list[RealSeriesComparison] = []
        aggregate_errors: dict[RealBaselineMethod, list[float]] = defaultdict(list)
        aggregate_actuals: list[float] = []
        aggregate_predictions: dict[RealBaselineMethod, list[float]] = defaultdict(list)
        for source_id in sorted(grouped):
            ordered = sorted(grouped[source_id], key=lambda item: (item[0], item[2]))
            values = [item[1] for item in ordered]
            if len(values) > effective.max_rows_per_series:
                values = values[-effective.max_rows_per_series:]
            lag = effective.lag_steps
            if len(values) < max(effective.minimum_samples, lag + 2):
                continue
            predictions, actuals, model_fingerprint = _fit_and_predict(
                source_id, values, effective
            )
            training_target_count = len(values) - lag
            test_count = len(actuals)
            train_values = values[:lag + training_target_count]
            persistence = tuple(train_values[-1] for _ in actuals)
            rolling_window = min(effective.rolling_window, len(train_values))
            rolling_value = sum(train_values[-rolling_window:]) / rolling_window
            rolling = tuple(rolling_value for _ in actuals)
            methods = (
                (RealBaselineMethod.PERSISTENCE, persistence),
                (RealBaselineMethod.ROLLING_MEAN, rolling),
                (RealBaselineMethod.PHASE61_RIDGE, predictions),
            )
            metrics = tuple(_metrics(method, actuals, forecast) for method, forecast in methods)
            series_results.append(RealSeriesComparison(
                source_id=source_id,
                sample_count=len(values),
                training_samples=training_target_count,
                test_samples=test_count,
                metrics=metrics,
                phase61_model_fingerprint=model_fingerprint,
            ))
            aggregate_actuals.extend(actuals)
            for method, forecast in methods:
                aggregate_predictions[method].extend(forecast)
                aggregate_errors[method].extend(
                    prediction - actual
                    for prediction, actual in zip(forecast, actuals, strict=True)
                )
        if not series_results:
            raise ValueError("no eligible real telemetry series for baseline comparison")
        aggregate_metrics = tuple(
            _metrics(method, tuple(aggregate_actuals), tuple(aggregate_predictions[method]))
            for method in RealBaselineMethod
        )
        payload = {
            "dataset_path": path.as_posix(),
            "source_sha256": source_sha256,
            "row_count": row_count,
            "series_results": [item.model_dump(mode="json") for item in series_results],
            "aggregate_metrics": [item.model_dump(mode="json") for item in aggregate_metrics],
            "config": effective.model_dump(mode="json"),
        }
        return RealBaselineComparisonReport(
            status="pass",
            evidence_class="PUBLIC DATA",
            dataset_path=path.as_posix(),
            source_sha256=source_sha256,
            provenance_verified=True,
            row_count=row_count,
            series_count=len(grouped),
            compared_series_count=len(series_results),
            aggregate_metrics=aggregate_metrics,
            series_results=tuple(series_results),
            comparison_fingerprint=_fingerprint(payload),
            network_mutation=False,
        )
