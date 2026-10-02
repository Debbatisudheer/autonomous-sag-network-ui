from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sag_network.real_failure_intelligence.models import (
    RealFailureEvidence,
    RealFailureIntelligenceConfig,
    RealFailureIntelligenceReport,
    RealFailureSeries,
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


def _parse_anomaly(row: dict[str, str]) -> bool:
    raw_anomaly = row.get("anomaly", "").strip().lower()
    if raw_anomaly in {"1", "true", "yes", "y", "anomaly", "abnormal"}:
        return True
    raw_label = row.get("label", "").strip().lower()
    return raw_label in {"1", "true", "yes", "y", "anomaly", "abnormal"}


def _split_series(
    rows: list[tuple[float, float, bool, int]],
    config: RealFailureIntelligenceConfig,
) -> tuple[
    list[tuple[float, float, bool, int]],
    list[tuple[float, float, bool, int]],
    list[tuple[float, float, bool, int]],
]:
    if len(rows) < config.minimum_samples:
        return [], [], []
    target_count = len(rows) - config.lag_steps
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
        rows[:fit_end],
        rows[fit_end:calibration_end],
        rows[calibration_end:],
    )


def _fit_parameters(
    values: list[float],
    config: RealFailureIntelligenceConfig,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], float, float]:
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(config.lag_steps, len(values)):
        features.append(
            _features(values[index - config.lag_steps : index], config.lag_steps)
        )
        targets.append(values[index])
    means = tuple(
        sum(row[index] for row in features) / len(features)
        for index in range(len(features[0]))
    )
    raw_scales = [
        math.sqrt(
            sum((row[index] - means[index]) ** 2 for row in features)
            / len(features)
        )
        for index in range(len(means))
    ]
    scales = tuple(scale if scale > 1e-12 else 1.0 for scale in raw_scales)
    target_mean = sum(targets) / len(targets)
    raw_target_scale = math.sqrt(
        sum((value - target_mean) ** 2 for value in targets) / len(targets)
    )
    target_scale = raw_target_scale if raw_target_scale > 1e-12 else 1.0
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
    return coefficients, means, scales, target_mean, target_scale


def _predict(
    values: list[float],
    parameters: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], float, float],
    config: RealFailureIntelligenceConfig,
) -> tuple[float, ...]:
    coefficients, means, scales, target_mean, target_scale = parameters
    predictions: list[float] = []
    for index in range(config.lag_steps, len(values)):
        feature_row = _features(
            values[index - config.lag_steps : index],
            config.lag_steps,
        )
        normalized = [
            (value - mean) / scale
            for value, mean, scale in zip(feature_row, means, scales, strict=True)
        ]
        predictions.append(
            target_mean
            + target_scale
            * (
                coefficients[0]
                + sum(
                    coefficient * value
                    for coefficient, value in zip(
                        coefficients[1:], normalized, strict=True
                    )
                )
            )
        )
    return tuple(predictions)


def _conformal_quantile(residuals: list[float], confidence_level: float) -> float:
    ordered = sorted(abs(value) for value in residuals if math.isfinite(value))
    if not ordered:
        return 0.0
    rank = math.ceil((len(ordered) + 1) * confidence_level)
    index = min(len(ordered), max(1, rank)) - 1
    return ordered[index]


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute a quantile from an empty series")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _risk_score(
    predicted_value: float,
    lower_bound: float,
    upper_bound: float,
    normal_lower: float,
    normal_upper: float,
    conformal_quantile: float,
) -> float:
    scale = max(conformal_quantile, 1e-12)
    distances = [
        max(0.0, normal_lower - predicted_value),
        max(0.0, predicted_value - normal_upper),
        max(0.0, normal_lower - lower_bound),
        max(0.0, upper_bound - normal_upper),
    ]
    return max(0.0, min(1.0, max(distances) / scale))


def _classification_metrics(
    predicted_flags: list[bool],
    observed_flags: list[bool],
) -> tuple[int, int, int, int, float, float, float]:
    true_positive = sum(predicted and observed for predicted, observed in zip(predicted_flags, observed_flags, strict=True))
    false_positive = sum(predicted and not observed for predicted, observed in zip(predicted_flags, observed_flags, strict=True))
    false_negative = sum((not predicted) and observed for predicted, observed in zip(predicted_flags, observed_flags, strict=True))
    true_negative = len(predicted_flags) - true_positive - false_positive - false_negative
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return true_positive, false_positive, false_negative, true_negative, precision, recall, f1


class RealFailureIntelligenceRunner:
    """Generate deterministic predictive anomaly/failure-risk intelligence from real telemetry."""

    def run(
        self,
        path: Path,
        *,
        config: RealFailureIntelligenceConfig | None = None,
        evidence_class: RealFailureEvidence = RealFailureEvidence.PUBLIC_DATA,
    ) -> RealFailureIntelligenceReport:
        effective = config or RealFailureIntelligenceConfig()
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
        if evidence_class is RealFailureEvidence.PUBLIC_DATA and not provenance_verified:
            raise ValueError(
                "public-data failure intelligence requires a verified provenance manifest"
            )

        grouped: dict[str, list[tuple[float, float, bool, int]]] = defaultdict(list)
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
                        (timestamp, value, _parse_anomaly(row), row_count)
                    )

        series_results: list[RealFailureSeries] = []
        total_observed = 0
        total_flagged = 0
        total_tp = 0
        total_fp = 0
        total_fn = 0
        risk_scores: list[float] = []

        for source_id in sorted(grouped):
            ordered = sorted(grouped[source_id], key=lambda item: (item[0], item[3]))
            if len(ordered) > effective.max_rows_per_series:
                ordered = ordered[-effective.max_rows_per_series :]
            fit_rows, calibration_rows, test_rows = _split_series(ordered, effective)
            if not fit_rows or not calibration_rows or not test_rows:
                continue

            fit_values = [item[1] for item in fit_rows]
            calibration_values = [item[1] for item in calibration_rows]
            test_values = [item[1] for item in test_rows]
            parameters = _fit_parameters(fit_values, effective)

            calibration_predictions = _predict(
                [*fit_values[-effective.lag_steps :], *calibration_values],
                parameters,
                effective,
            )[-len(calibration_values) :]
            calibration_residuals = [
                actual - predicted
                for actual, predicted in zip(
                    calibration_values, calibration_predictions, strict=True
                )
            ]
            if len(calibration_residuals) < effective.minimum_calibration_samples:
                continue
            conformal_quantile = _conformal_quantile(
                calibration_residuals,
                effective.confidence_level,
            )

            test_predictions = _predict(
                [*fit_values[-effective.lag_steps :], *test_values],
                parameters,
                effective,
            )[-len(test_values) :]
            normal_lower = _quantile(fit_values, effective.normal_lower_quantile)
            normal_upper = _quantile(fit_values, effective.normal_upper_quantile)

            observed_flags = [item[2] for item in test_rows]
            predicted_flags: list[bool] = []
            series_risk_scores: list[float] = []
            for prediction in test_predictions:
                lower_bound = prediction - conformal_quantile
                upper_bound = prediction + conformal_quantile
                score = _risk_score(
                    prediction,
                    lower_bound,
                    upper_bound,
                    normal_lower,
                    normal_upper,
                    conformal_quantile,
                )
                series_risk_scores.append(score)
                predicted_flags.append(score > 0.0)

            tp, fp, fn, _, precision, recall, f1 = _classification_metrics(
                predicted_flags,
                observed_flags,
            )
            fit_sample_count = len(fit_values) - effective.lag_steps
            calibration_sample_count = len(calibration_values)
            test_sample_count = len(test_values)
            conformal_quantile = float(conformal_quantile)
            normal_lower_bound = float(normal_lower)
            normal_upper_bound = float(normal_upper)
            observed_anomaly_count = sum(observed_flags)
            flagged_risk_count = sum(predicted_flags)
            true_positive_count = tp
            false_positive_count = fp
            false_negative_count = fn
            mean_risk_score = sum(series_risk_scores) / len(series_risk_scores)
            max_risk_score = max(series_risk_scores)

            series_payload = {
                "fit_samples": fit_sample_count,
                "calibration_samples": calibration_sample_count,
                "test_samples": test_sample_count,
                "conformal_quantile": conformal_quantile,
                "normal_lower_bound": normal_lower_bound,
                "normal_upper_bound": normal_upper_bound,
                "observed_anomaly_count": observed_anomaly_count,
                "flagged_risk_count": flagged_risk_count,
                "true_positive_count": true_positive_count,
                "false_positive_count": false_positive_count,
                "false_negative_count": false_negative_count,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "mean_risk_score": mean_risk_score,
                "max_risk_score": max_risk_score,
            }
            series_fingerprint = _fingerprint(
                {"source_id": source_id, **series_payload}
            )
            series_results.append(
                RealFailureSeries(
                    source_id=source_id,
                    sample_count=len(ordered),
                    fit_samples=fit_sample_count,
                    calibration_samples=calibration_sample_count,
                    test_samples=test_sample_count,
                    conformal_quantile=conformal_quantile,
                    normal_lower_bound=normal_lower_bound,
                    normal_upper_bound=normal_upper_bound,
                    observed_anomaly_count=observed_anomaly_count,
                    flagged_risk_count=flagged_risk_count,
                    true_positive_count=true_positive_count,
                    false_positive_count=false_positive_count,
                    false_negative_count=false_negative_count,
                    precision=precision,
                    recall=recall,
                    f1_score=f1,
                    mean_risk_score=mean_risk_score,
                    max_risk_score=max_risk_score,
                    series_fingerprint=series_fingerprint,
                )
            )
            total_observed += sum(observed_flags)
            total_flagged += sum(predicted_flags)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            risk_scores.extend(series_risk_scores)

        if not series_results:
            raise ValueError("no eligible real telemetry series for failure intelligence")

        precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
        recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        payload = {
            "dataset_path": path.as_posix(),
            "source_sha256": source_sha256,
            "row_count": row_count,
            "config": effective.model_dump(mode="json"),
            "series_results": [item.model_dump(mode="json") for item in series_results],
            "observed_anomaly_count": total_observed,
            "flagged_risk_count": total_flagged,
            "true_positive_count": total_tp,
            "false_positive_count": total_fp,
            "false_negative_count": total_fn,
        }
        return RealFailureIntelligenceReport(
            status="pass",
            evidence_class=evidence_class,
            dataset_path=path.as_posix(),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            row_count=row_count,
            series_count=len(grouped),
            analyzed_series_count=len(series_results),
            confidence_level=effective.confidence_level,
            observed_anomaly_count=total_observed,
            flagged_risk_count=total_flagged,
            true_positive_count=total_tp,
            false_positive_count=total_fp,
            false_negative_count=total_fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            mean_risk_score=sum(risk_scores) / len(risk_scores),
            max_risk_score=max(risk_scores),
            series_results=tuple(series_results),
            intelligence_fingerprint=_fingerprint(payload),
            network_mutation=False,
        )
