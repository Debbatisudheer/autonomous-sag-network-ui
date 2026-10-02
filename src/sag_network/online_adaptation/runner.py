from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sag_network.online_adaptation.models import (
    OnlineAdaptationConfig,
    OnlineAdaptationEvidence,
    OnlineAdaptationReport,
    OnlineAdaptationSeries,
    OnlineMetric,
)
from sag_network.real_training.trainer import _features, _fit_ridge


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_timestamp(value: str) -> float:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        parsed = datetime.fromisoformat(stripped)
        if parsed.tzinfo is None:
            raise ValueError(
                "ISO-8601 timestamp must include timezone information"
            )
        return parsed.timestamp()


def _fit_parameters(
    values: list[float],
    config: OnlineAdaptationConfig,
) -> tuple[
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    float,
    float,
]:
    if len(values) <= config.lag_steps:
        raise ValueError("insufficient values for model fitting")

    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(config.lag_steps, len(values)):
        features.append(
            _features(
                values[index - config.lag_steps : index],
                config.lag_steps,
            )
        )
        targets.append(values[index])

    means = tuple(
        sum(row[index] for row in features) / len(features)
        for index in range(len(features[0]))
    )
    scales_list = [
        math.sqrt(
            sum((row[index] - means[index]) ** 2 for row in features)
            / len(features)
        )
        for index in range(len(means))
    ]
    scales = tuple(
        scale if scale > 1e-12 else 1.0
        for scale in scales_list
    )
    target_mean = sum(targets) / len(targets)
    target_scale_value = math.sqrt(
        sum((value - target_mean) ** 2 for value in targets)
        / len(targets)
    )
    target_scale = (
        target_scale_value
        if target_scale_value > 1e-12
        else 1.0
    )

    normalized_features = [
        [
            (value - mean) / scale
            for value, mean, scale in zip(
                row,
                means,
                scales,
                strict=True,
            )
        ]
        for row in features
    ]
    normalized_targets = [
        (value - target_mean) / target_scale
        for value in targets
    ]
    coefficients = _fit_ridge(
        normalized_features,
        normalized_targets,
        config.ridge_alpha,
    )
    return (
        coefficients,
        means,
        scales,
        target_mean,
        target_scale,
    )


def _predict_one(
    history: list[float],
    parameters: tuple[
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        float,
        float,
    ],
    config: OnlineAdaptationConfig,
) -> float:
    coefficients, means, scales, target_mean, target_scale = parameters
    feature_row = _features(
        history[-config.lag_steps :],
        config.lag_steps,
    )
    normalized = [
        (value - mean) / scale
        for value, mean, scale in zip(
            feature_row,
            means,
            scales,
            strict=True,
        )
    ]
    return target_mean + target_scale * (
        coefficients[0]
        + sum(
            coefficient * value
            for coefficient, value in zip(
                coefficients[1:],
                normalized,
                strict=True,
            )
        )
    )


def _metric(
    method: str,
    actuals: list[float],
    predictions: list[float],
) -> OnlineMetric:
    errors = [
        prediction - actual
        for prediction, actual in zip(
            predictions,
            actuals,
            strict=True,
        )
    ]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(
        sum(error * error for error in errors) / len(errors)
    )
    mean_actual = sum(actuals) / len(actuals)
    total = sum(
        (actual - mean_actual) ** 2
        for actual in actuals
    )
    residual = sum(error * error for error in errors)
    r_squared = (
        1.0
        if total == 0.0 and residual == 0.0
        else 0.0
        if total == 0.0
        else 1.0 - residual / total
    )
    return OnlineMetric(
        method=method,
        sample_count=len(actuals),
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        r_squared=r_squared,
    )


def _reference_statistics(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    std = math.sqrt(
        sum((value - mean) ** 2 for value in values) / len(values)
    )
    return mean, std


def _shift_score(
    reference_mean: float,
    reference_std: float,
    recent: list[float],
) -> float:
    if not recent:
        return 0.0
    recent_mean = sum(recent) / len(recent)
    recent_std = math.sqrt(
        sum((value - recent_mean) ** 2 for value in recent)
        / len(recent)
    )
    standardized_mean = abs(recent_mean - reference_mean) / max(
        reference_std,
        1e-12,
    )
    if reference_std <= 1e-12 and recent_std <= 1e-12:
        ratio = 1.0
    elif reference_std <= 1e-12:
        ratio = float("inf")
    else:
        ratio = max(
            recent_std / reference_std,
            reference_std / max(recent_std, 1e-12),
        )
    mean_component = min(
        1.0,
        standardized_mean / 0.5,
    )
    ratio_component = min(
        1.0,
        max(0.0, ratio - 1.0) / 0.5,
    )
    return max(mean_component, ratio_component)


def _run_series(
    source_id: str,
    values: list[float],
    config: OnlineAdaptationConfig,
) -> tuple[
    OnlineAdaptationSeries,
    list[float],
    list[float],
    list[float],
] | None:
    if len(values) > config.max_rows_per_series:
        values = values[-config.max_rows_per_series :]

    target_count = len(values) - config.lag_steps
    if target_count < config.minimum_samples:
        return None

    stream_size = max(
        1,
        math.ceil(target_count * config.test_fraction),
    )
    initial_target_count = target_count - stream_size
    initial_value_count = config.lag_steps + initial_target_count
    if initial_target_count < config.minimum_samples:
        return None

    initial_history = values[:initial_value_count]
    stream_values = values[initial_value_count:]
    static_parameters = _fit_parameters(
        initial_history,
        config,
    )
    adaptive_parameters = static_parameters
    adaptation_history = list(initial_history)
    reference_mean, reference_std = _reference_statistics(
        initial_history
    )

    static_actuals: list[float] = []
    static_predictions: list[float] = []
    adaptive_predictions: list[float] = []
    scheduled_updates = 0
    shift_triggered_updates = 0
    total_updates = 0

    for stream_index, actual in enumerate(
        stream_values,
        start=1,
    ):
        static_prediction = _predict_one(
            adaptation_history,
            static_parameters,
            config,
        )
        adaptive_prediction = _predict_one(
            adaptation_history,
            adaptive_parameters,
            config,
        )

        static_actuals.append(actual)
        static_predictions.append(static_prediction)
        adaptive_predictions.append(adaptive_prediction)

        adaptation_history.append(actual)
        if len(adaptation_history) > config.adaptation_window:
            adaptation_history = adaptation_history[-config.adaptation_window :]

        recent_window = adaptation_history[-config.shift_window :]
        shift_score = _shift_score(
            reference_mean,
            reference_std,
            recent_window,
        )
        scheduled = stream_index % config.update_interval == 0
        shifted = shift_score >= config.shift_threshold
        initial_update = (
            config.force_initial_adaptation
            and stream_index == 1
        )
        should_update = scheduled or shifted or initial_update

        if (
            should_update
            and len(adaptation_history)
            >= config.minimum_adaptation_samples
        ):
            adaptive_parameters = _fit_parameters(
                adaptation_history,
                config,
            )
            total_updates += 1
            if scheduled:
                scheduled_updates += 1
            if shifted:
                shift_triggered_updates += 1

    static_metric = _metric(
        "phase61_static",
        static_actuals,
        static_predictions,
    )
    adaptive_metric = _metric(
        "online_adaptive_ridge",
        static_actuals,
        adaptive_predictions,
    )
    payload = {
        "source_id": source_id,
        "sample_count": len(values),
        "initial_fit_samples": initial_target_count,
        "stream_samples": len(stream_values),
        "static_metric": static_metric.model_dump(
            mode="json"
        ),
        "adaptive_metric": adaptive_metric.model_dump(
            mode="json"
        ),
        "scheduled_updates": scheduled_updates,
        "shift_triggered_updates": shift_triggered_updates,
        "total_updates": total_updates,
        "adaptation_window": config.adaptation_window,
        "shift_window": config.shift_window,
        "shift_threshold": config.shift_threshold,
    }
    result = OnlineAdaptationSeries(
        source_id=source_id,
        sample_count=len(values),
        initial_fit_samples=initial_target_count,
        stream_samples=len(stream_values),
        static_metrics=static_metric,
        adaptive_metrics=adaptive_metric,
        scheduled_update_count=scheduled_updates,
        shift_triggered_update_count=shift_triggered_updates,
        total_update_count=total_updates,
        adaptation_window=config.adaptation_window,
        shift_threshold=config.shift_threshold,
        adaptation_delta_mae=(
            adaptive_metric.mean_absolute_error
            - static_metric.mean_absolute_error
        ),
        series_fingerprint=_fingerprint(payload),
    )
    return (
        result,
        static_actuals,
        static_predictions,
        adaptive_predictions,
    )


class RealOnlineModelAdaptationRunner:
    """Run leakage-free prequential adaptation on historical telemetry."""

    def run(
        self,
        path: Path,
        *,
        config: OnlineAdaptationConfig | None = None,
        evidence_class: OnlineAdaptationEvidence = OnlineAdaptationEvidence.PUBLIC_DATA,
    ) -> OnlineAdaptationReport:
        effective = config or OnlineAdaptationConfig()
        if not path.is_file():
            raise FileNotFoundError(
                f"dataset does not exist: {path}"
            )

        source_sha256 = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        manifest_path = path.with_suffix(
            path.suffix + ".manifest.json"
        )
        provenance_verified = False
        if manifest_path.is_file():
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            if manifest.get("sha256") != source_sha256:
                raise ValueError(
                    "provenance manifest SHA-256 does not match the dataset"
                )
            provenance_verified = manifest.get("verified") is True
        if (
            evidence_class is OnlineAdaptationEvidence.PUBLIC_DATA
            and not provenance_verified
        ):
            raise ValueError(
                "public-data online adaptation requires a verified provenance manifest"
            )

        grouped: dict[
            str,
            list[tuple[float, float, int]],
        ] = defaultdict(list)
        row_count = 0
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            reader = csv.DictReader(stream)
            required = {
                "timestamp",
                "channel",
                "value",
            }
            if not required.issubset(
                set(reader.fieldnames or ())
            ):
                raise ValueError(
                    "dataset must contain timestamp, channel, and value columns"
                )
            for row in reader:
                row_count += 1
                try:
                    timestamp = _parse_timestamp(
                        row["timestamp"]
                    )
                    value = float(row["value"])
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"non-numeric timestamp/value at row {row_count + 1}"
                    ) from exc
                if not math.isfinite(timestamp) or not math.isfinite(value):
                    continue
                train_flag = int(
                    float(row.get("train", "1") or "1")
                )
                if train_flag == 1:
                    grouped[
                        row["channel"].strip() or "opssat"
                    ].append(
                        (timestamp, value, row_count)
                    )

        results: list[OnlineAdaptationSeries] = []
        aggregate_actuals: list[float] = []
        aggregate_static_predictions: list[float] = []
        aggregate_adaptive_predictions: list[float] = []
        total_scheduled = 0
        total_shift = 0
        total_updates = 0

        for source_id in sorted(grouped):
            ordered = sorted(
                grouped[source_id],
                key=lambda item: (item[0], item[2]),
            )
            run_result = _run_series(
                source_id,
                [item[1] for item in ordered],
                effective,
            )
            if run_result is None:
                continue
            result, actuals, static_predictions, adaptive_predictions = run_result
            results.append(result)
            aggregate_actuals.extend(actuals)
            aggregate_static_predictions.extend(static_predictions)
            aggregate_adaptive_predictions.extend(adaptive_predictions)
            total_scheduled += result.scheduled_update_count
            total_shift += result.shift_triggered_update_count
            total_updates += result.total_update_count

        if not results:
            raise ValueError(
                "no eligible real telemetry series for online model adaptation"
            )

        aggregate_static_metric = _metric(
            "phase61_static",
            aggregate_actuals,
            aggregate_static_predictions,
        )
        aggregate_adaptive_metric = _metric(
            "online_adaptive_ridge",
            aggregate_actuals,
            aggregate_adaptive_predictions,
        )
        payload = {
            "dataset_path": path.as_posix(),
            "source_sha256": source_sha256,
            "row_count": row_count,
            "config": effective.model_dump(mode="json"),
            "series_results": [
                result.model_dump(mode="json")
                for result in results
            ],
            "aggregate_static": aggregate_static_metric.model_dump(
                mode="json"
            ),
            "aggregate_adaptive": aggregate_adaptive_metric.model_dump(
                mode="json"
            ),
        }
        return OnlineAdaptationReport(
            status="pass",
            evidence_class=evidence_class,
            dataset_path=path.as_posix(),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            row_count=row_count,
            series_count=len(grouped),
            adapted_series_count=len(results),
            aggregate_stream_sample_count=len(aggregate_actuals),
            aggregate_static_metrics=aggregate_static_metric,
            aggregate_adaptive_metrics=aggregate_adaptive_metric,
            aggregate_adaptation_delta_mae=(
                aggregate_adaptive_metric.mean_absolute_error
                - aggregate_static_metric.mean_absolute_error
            ),
            total_scheduled_update_count=total_scheduled,
            total_shift_triggered_update_count=total_shift,
            total_update_count=total_updates,
            series_results=tuple(results),
            adaptation_fingerprint=_fingerprint(payload),
            network_mutation=False,
        )
