from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from sag_network.real_training.models import (
    RealDataTrainingConfig,
    RealDataTrainingReport,
    RealDataTrainingResult,
    TrainingEvidence,
)


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_timestamp(value: str) -> float:
    """Parse numeric or timezone-aware ISO-8601 telemetry timestamps."""
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        pass
    normalized = stripped
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("ISO-8601 timestamp must include timezone information")
    return parsed.timestamp()


def _fit_ridge(features: list[list[float]], targets: list[float], alpha: float) -> tuple[float, ...]:
    dimension = len(features[0])
    size = dimension + 1
    matrix: list[list[float]] = [[0.0 for _ in range(size)] for _ in range(size)]
    vector: list[float] = [0.0 for _ in range(size)]
    for feature_row, target in zip(features, targets, strict=True):
        augmented = [1.0, *feature_row]
        for feature_index in range(size):
            vector[feature_index] += augmented[feature_index] * target
            for matrix_index in range(size):
                matrix[feature_index][matrix_index] += augmented[feature_index] * augmented[matrix_index]
    for regularized_index in range(1, size):
        matrix[regularized_index][regularized_index] += alpha
    for pivot_column in range(size):
        pivot_row = max(range(pivot_column, size), key=lambda candidate: abs(matrix[candidate][pivot_column]))
        if abs(matrix[pivot_row][pivot_column]) < 1e-12:
            raise ValueError("singular regression system")
        if pivot_row != pivot_column:
            matrix[pivot_column], matrix[pivot_row] = matrix[pivot_row], matrix[pivot_column]
            vector[pivot_column], vector[pivot_row] = vector[pivot_row], vector[pivot_column]
        pivot_value = matrix[pivot_column][pivot_column]
        for elimination_row in range(pivot_column + 1, size):
            factor = matrix[elimination_row][pivot_column] / pivot_value
            for elimination_column in range(pivot_column, size):
                matrix[elimination_row][elimination_column] -= factor * matrix[pivot_column][elimination_column]
            vector[elimination_row] -= factor * vector[pivot_column]
    solution: list[float] = [0.0] * size
    for solution_row in range(size - 1, -1, -1):
        remainder = vector[solution_row] - sum(
            matrix[solution_row][solution_column] * solution[solution_column]
            for solution_column in range(solution_row + 1, size)
        )
        solution[solution_row] = remainder / matrix[solution_row][solution_row]
    return tuple(solution)


def _features(values: list[float], lag_steps: int) -> list[float]:
    recent = values[-lag_steps:]
    return [*reversed(recent), recent[-1] - recent[-2], sum(recent) / len(recent)]


def _train_series(
    source_id: str, values: list[float], config: RealDataTrainingConfig
) -> RealDataTrainingResult | None:
    if len(values) > config.max_rows_per_series:
        values = values[-config.max_rows_per_series :]
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(config.lag_steps, len(values)):
        features.append(_features(values[index - config.lag_steps : index], config.lag_steps))
        targets.append(values[index])
    if len(targets) < config.minimum_samples:
        return None
    test_size = max(1, math.ceil(len(targets) * config.test_fraction))
    train_size = len(targets) - test_size
    train_features = features[:train_size]
    train_targets = targets[:train_size]
    means = [sum(row[index] for row in train_features) / train_size for index in range(len(train_features[0]))]
    scales = [
        math.sqrt(sum((row[index] - means[index]) ** 2 for row in train_features) / train_size)
        for index in range(len(means))
    ]
    scales = [scale if scale > 1e-12 else 1.0 for scale in scales]
    target_mean = sum(train_targets) / train_size
    target_scale = math.sqrt(sum((value - target_mean) ** 2 for value in train_targets) / train_size)
    target_scale = target_scale if target_scale > 1e-12 else 1.0
    normalized_train = [[(value - mean) / scale for value, mean, scale in zip(row, means, scales, strict=True)] for row in train_features]
    normalized_targets = [(value - target_mean) / target_scale for value in train_targets]
    coefficients = _fit_ridge(normalized_train, normalized_targets, config.ridge_alpha)
    normalized_test = [[(value - mean) / scale for value, mean, scale in zip(row, means, scales, strict=True)] for row in features[train_size:]]
    predictions = [
        target_mean + target_scale * (
            coefficients[0]
            + sum(coefficient * value for coefficient, value in zip(coefficients[1:], row, strict=True))
        )
        for row in normalized_test
    ]
    test_targets = targets[train_size:]
    errors = [prediction - target for prediction, target in zip(predictions, test_targets, strict=True)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean_target = sum(test_targets) / len(test_targets)
    total = sum((target - mean_target) ** 2 for target in test_targets)
    residual = sum(error * error for error in errors)
    r_squared = 1.0 if total == 0 and residual == 0 else (0.0 if total == 0 else 1.0 - residual / total)
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
    return RealDataTrainingResult(
        source_id=source_id,
        sample_count=len(values),
        training_samples=train_size,
        test_samples=test_size,
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        r_squared=r_squared,
        model_fingerprint=_fingerprint(model_payload),
    )


class RealDataModelTrainer:
    """Train a deterministic next-step model from the verified public telemetry CSV."""

    def train_csv(
        self,
        path: Path,
        *,
        config: RealDataTrainingConfig | None = None,
        evidence_class: TrainingEvidence = TrainingEvidence.PUBLIC_DATA,
    ) -> RealDataTrainingReport:
        effective = config or RealDataTrainingConfig()
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
        if evidence_class is TrainingEvidence.PUBLIC_DATA and not provenance_verified:
            raise ValueError("public-data training requires a verified provenance manifest")

        grouped: dict[str, list[tuple[float, float, int]]] = {}
        row_count = 0
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"timestamp", "channel", "value"}
            if not required.issubset(set(reader.fieldnames or ())):
                raise ValueError("dataset must contain timestamp, channel, and value columns")
            for row in reader:
                row_count += 1
                try:
                    timestamp = float(row["timestamp"])
                    value = float(row["value"])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"non-numeric timestamp/value at row {row_count + 1}") from exc
                if not math.isfinite(timestamp) or not math.isfinite(value):
                    continue
                channel = row["channel"].strip() or "opssat"
                train_flag = int(float(row.get("train", "1") or "1"))
                if train_flag == 1:
                    grouped.setdefault(channel, []).append((timestamp, value, row_count))

        results: list[RealDataTrainingResult] = []
        for channel in sorted(grouped):
            ordered = sorted(grouped[channel], key=lambda item: (item[0], item[2]))
            result = _train_series(channel, [item[1] for item in ordered], effective)
            if result is not None:
                results.append(result)

        payload = {
            "dataset": path.name,
            "source_sha256": source_sha256,
            "provenance_verified": provenance_verified,
            "row_count": row_count,
            "series": [item.model_dump(mode="json") for item in results],
            "config": effective.model_dump(mode="json"),
        }
        return RealDataTrainingReport(
            dataset_path=path.as_posix(),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            row_count=row_count,
            series_count=len(grouped),
            trained_series_count=len(results),
            results=results,
            training_fingerprint=_fingerprint(payload),
            evidence_class=evidence_class,
            status="pass",
        )
