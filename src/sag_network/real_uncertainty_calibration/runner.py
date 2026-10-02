from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sag_network.real_training.trainer import _features, _fit_ridge
from sag_network.real_uncertainty_calibration.models import (
    RealUncertaintyCalibrationConfig,
    RealUncertaintyCalibrationReport,
    RealUncertaintyEvidence,
    RealUncertaintySeries,
)


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


def _split(values: list[float], config: RealUncertaintyCalibrationConfig) -> tuple[
    list[float], list[float], list[float]
]:
    if len(values) < config.minimum_samples:
        return [], [], []
    target_count = len(values) - config.lag_steps
    if target_count < config.minimum_samples:
        return [], [], []
    test_size = max(1, math.ceil(target_count * config.test_fraction))
    train_and_calibration = target_count - test_size
    calibration_size = max(
        config.minimum_calibration_samples,
        math.ceil(target_count * config.calibration_fraction),
    )
    fit_size = train_and_calibration - calibration_size
    if fit_size < config.minimum_samples or calibration_size < config.minimum_calibration_samples:
        return [], [], []
    fit_end = config.lag_steps + fit_size
    calibration_end = fit_end + calibration_size
    return (
        values[:fit_end],
        values[fit_end:calibration_end],
        values[calibration_end:],
    )


def _predict(
    values: list[float],
    coefficients: tuple[float, ...],
    means: tuple[float, ...],
    scales: tuple[float, ...],
    target_mean: float,
    target_scale: float,
    config: RealUncertaintyCalibrationConfig,
) -> tuple[float, ...]:
    predictions: list[float] = []
    for index in range(config.lag_steps, len(values)):
        feature_row = _features(
            values[index - config.lag_steps : index],
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
        predictions.append(
            target_mean
            + target_scale
            * (
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
        )
    return tuple(predictions)


def _fit_model_parameters(
    source_id: str,
    values: list[float],
    config: RealUncertaintyCalibrationConfig,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], float, float, str]:
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
    scales = tuple(scale if scale > 1e-12 else 1.0 for scale in scales_list)
    target_mean = sum(targets) / len(targets)
    target_scale_value = math.sqrt(
        sum((value - target_mean) ** 2 for value in targets)
        / len(targets)
    )
    target_scale = target_scale_value if target_scale_value > 1e-12 else 1.0
    normalized_features = [
        [
            (value - mean) / scale
            for value, mean, scale in zip(row, means, scales, strict=True)
        ]
        for row in features
    ]
    normalized_targets = [
        (value - target_mean) / target_scale for value in targets
    ]
    coefficients = _fit_ridge(
        normalized_features,
        normalized_targets,
        config.ridge_alpha,
    )
    model_payload = {
        "source_id": source_id,
        "lag_steps": config.lag_steps,
        "coefficients": coefficients,
        "feature_means": list(means),
        "feature_scales": list(scales),
        "target_mean": target_mean,
        "target_scale": target_scale,
        "training_samples": len(targets),
    }
    return (
        coefficients,
        means,
        scales,
        target_mean,
        target_scale,
        _fingerprint(model_payload),
    )


def _conformal_quantile(residuals: list[float], confidence_level: float) -> float:
    if not residuals:
        return 0.0
    ordered = sorted(abs(value) for value in residuals if math.isfinite(value))
    if not ordered:
        return 0.0
    rank = math.ceil((len(ordered) + 1) * confidence_level)
    index = min(len(ordered), max(1, rank)) - 1
    return ordered[index]


class RealDataUncertaintyCalibrationRunner:
    """Calibrate real-data next-step prediction intervals with split conformal residuals."""

    def run(
        self,
        path: Path,
        *,
        config: RealUncertaintyCalibrationConfig | None = None,
        evidence_class: RealUncertaintyEvidence = RealUncertaintyEvidence.PUBLIC_DATA,
    ) -> RealUncertaintyCalibrationReport:
        effective = config or RealUncertaintyCalibrationConfig()
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
        if (
            evidence_class is RealUncertaintyEvidence.PUBLIC_DATA
            and not provenance_verified
        ):
            raise ValueError(
                "public-data uncertainty calibration requires a verified provenance manifest"
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
                    raise ValueError(
                        f"non-numeric timestamp/value at row {row_count + 1}"
                    ) from exc
                if not math.isfinite(timestamp) or not math.isfinite(value):
                    continue
                train_flag = int(float(row.get("train", "1") or "1"))
                if train_flag == 1:
                    grouped[row["channel"].strip() or "opssat"].append(
                        (timestamp, value, row_count)
                    )

        series_results: list[RealUncertaintySeries] = []
        aggregate_test_values: list[float] = []
        aggregate_predictions: list[float] = []
        aggregate_widths: list[float] = []
        aggregate_calibration_residuals: list[float] = []
        aggregate_quantiles: list[float] = []

        for source_id in sorted(grouped):
            ordered = sorted(grouped[source_id], key=lambda item: (item[0], item[2]))
            values = [item[1] for item in ordered]
            if len(values) > effective.max_rows_per_series:
                values = values[-effective.max_rows_per_series:]
            fit_values, calibration_values, test_values = _split(values, effective)
            if not fit_values or not calibration_values or not test_values:
                continue

            calibration_parameters = _fit_model_parameters(
                source_id,
                fit_values,
                effective,
            )
            (
                calibration_coefficients,
                calibration_means,
                calibration_scales,
                calibration_target_mean,
                calibration_target_scale,
                calibration_model_fingerprint,
            ) = calibration_parameters
            calibration_predictions = _predict(
                [*fit_values[-effective.lag_steps :], *calibration_values],
                calibration_coefficients,
                calibration_means,
                calibration_scales,
                calibration_target_mean,
                calibration_target_scale,
                effective,
            )
            calibration_predictions = calibration_predictions[-len(calibration_values) :]
            residuals = [
                prediction - actual
                for prediction, actual in zip(
                    calibration_predictions,
                    calibration_values,
                    strict=True,
                )
            ]
            if len(residuals) < effective.minimum_calibration_samples:
                continue
            quantile = _conformal_quantile(
                residuals,
                effective.confidence_level,
            )

            test_predictions = _predict(
                [*fit_values[-effective.lag_steps :], *test_values],
                calibration_coefficients,
                calibration_means,
                calibration_scales,
                calibration_target_mean,
                calibration_target_scale,
                effective,
            )
            test_predictions = test_predictions[-len(test_values) :]
            coverage_count = sum(
                abs(actual - prediction) <= quantile
                for actual, prediction in zip(
                    test_values,
                    test_predictions,
                    strict=True,
                )
            )
            empirical_coverage = coverage_count / len(test_values)
            widths = [2.0 * quantile] * len(test_values)
            calibration_residual_mae = sum(abs(value) for value in residuals) / len(residuals)
            coverage_status = (
                "meets_or_exceeds_target"
                if empirical_coverage >= effective.confidence_level
                else "below_target"
            )
            series_results.append(
                RealUncertaintySeries(
                    source_id=source_id,
                    sample_count=len(values),
                    fit_samples=len(fit_values) - effective.lag_steps,
                    calibration_samples=len(calibration_values),
                    test_samples=len(test_values),
                    confidence_level=effective.confidence_level,
                    calibration_quantile=quantile,
                    empirical_coverage=empirical_coverage,
                    coverage_gap=empirical_coverage - effective.confidence_level,
                    coverage_status=coverage_status,
                    mean_interval_width=sum(widths) / len(widths),
                    calibration_residual_mae=calibration_residual_mae,
                    interval_model_fingerprint=calibration_model_fingerprint,
                )
            )
            aggregate_test_values.extend(test_values)
            aggregate_predictions.extend(test_predictions)
            aggregate_widths.extend(widths)
            aggregate_calibration_residuals.extend(residuals)
            aggregate_quantiles.extend([quantile] * len(test_values))

        if not series_results:
            raise ValueError("no eligible real telemetry series for uncertainty calibration")

        aggregate_coverage = sum(
            abs(actual - prediction) <= quantile
            for actual, prediction, quantile in zip(
                aggregate_test_values,
                aggregate_predictions,
                aggregate_quantiles,
                strict=True,
            )
        )
        aggregate_empirical_coverage = aggregate_coverage / len(aggregate_test_values)
        aggregate_width = sum(aggregate_widths) / len(aggregate_widths)
        aggregate_residual_mae = sum(
            abs(value) for value in aggregate_calibration_residuals
        ) / len(aggregate_calibration_residuals)
        payload = {
            "dataset_path": path.as_posix(),
            "source_sha256": source_sha256,
            "row_count": row_count,
            "config": effective.model_dump(mode="json"),
            "series_results": [item.model_dump(mode="json") for item in series_results],
            "aggregate_empirical_coverage": aggregate_empirical_coverage,
        }
        return RealUncertaintyCalibrationReport(
            status="pass",
            evidence_class=evidence_class,
            dataset_path=path.as_posix(),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            row_count=row_count,
            series_count=len(grouped),
            calibrated_series_count=len(series_results),
            confidence_level=effective.confidence_level,
            calibration_method="split_conformal_absolute_residual",
            aggregate_test_sample_count=len(aggregate_test_values),
            aggregate_empirical_coverage=aggregate_empirical_coverage,
            aggregate_coverage_gap=aggregate_empirical_coverage - effective.confidence_level,
            aggregate_mean_interval_width=aggregate_width,
            aggregate_calibration_residual_mae=aggregate_residual_mae,
            series_results=tuple(series_results),
            calibration_fingerprint=_fingerprint(payload),
            network_mutation=False,
        )
