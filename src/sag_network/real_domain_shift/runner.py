from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sag_network.real_domain_shift.models import (
    DomainShiftConfig,
    DomainShiftEvidence,
    DomainShiftReport,
    DomainShiftSeries,
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


def _split_series(
    rows: list[tuple[float, float, int]],
    config: DomainShiftConfig,
) -> tuple[list[tuple[float, float, int]], list[tuple[float, float, int]], list[tuple[float, float, int]]]:
    if len(rows) < config.minimum_samples:
        return [], [], []
    target_count = len(rows) - config.lag_steps
    if target_count < config.minimum_samples:
        return [], [], []
    test_size = max(1, math.ceil(target_count * config.test_fraction))
    train_and_calibration = target_count - test_size
    calibration_size = max(
        config.minimum_comparison_samples,
        math.ceil(target_count * config.calibration_fraction),
    )
    fit_size = train_and_calibration - calibration_size
    if fit_size < config.minimum_samples or calibration_size < config.minimum_comparison_samples:
        return [], [], []
    fit_end = config.lag_steps + fit_size
    calibration_end = fit_end + calibration_size
    return (
        rows[:fit_end],
        rows[fit_end:calibration_end],
        rows[calibration_end:],
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    center = _mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / len(values))


def _histogram_proportions(
    reference: list[float],
    comparison: list[float],
    bins: int,
) -> tuple[list[float], list[float]]:
    minimum = min(reference)
    maximum = max(reference)
    if minimum == maximum:
        epsilon = max(abs(minimum) * 1e-12, 1e-12)
        edges = [minimum - epsilon, maximum + epsilon]
    else:
        step = (maximum - minimum) / bins
        edges = [minimum + index * step for index in range(bins + 1)]

    def counts(values: list[float]) -> list[int]:
        result = [0] * (len(edges) - 1)
        for value in values:
            if value <= edges[0]:
                index = 0
            elif value >= edges[-1]:
                index = len(result) - 1
            else:
                index = min(
                    len(result) - 1,
                    int((value - edges[0]) / (edges[-1] - edges[0]) * len(result)),
                )
            result[index] += 1
        return result

    reference_counts = counts(reference)
    comparison_counts = counts(comparison)
    reference_total = len(reference)
    comparison_total = len(comparison)
    return (
        [count / reference_total for count in reference_counts],
        [count / comparison_total for count in comparison_counts],
    )


def _psi(
    reference: list[float],
    comparison: list[float],
    bins: int,
) -> float:
    reference_proportions, comparison_proportions = _histogram_proportions(
        reference,
        comparison,
        bins,
    )
    epsilon = 1e-12
    value = 0.0
    for reference_probability, comparison_probability in zip(
        reference_proportions,
        comparison_proportions,
        strict=True,
    ):
        reference_probability = max(reference_probability, epsilon)
        comparison_probability = max(comparison_probability, epsilon)
        value += (
            comparison_probability - reference_probability
        ) * math.log(comparison_probability / reference_probability)
    return max(0.0, value)


def _empirical_cdf_distance(
    reference: list[float],
    comparison: list[float],
) -> float:
    reference_sorted = sorted(reference)
    comparison_sorted = sorted(comparison)
    reference_index = 0
    comparison_index = 0
    distance = 0.0
    total_reference = len(reference_sorted)
    total_comparison = len(comparison_sorted)
    while reference_index < total_reference or comparison_index < total_comparison:
        if comparison_index >= total_comparison or (
            reference_index < total_reference
            and reference_sorted[reference_index] <= comparison_sorted[comparison_index]
        ):
            value = reference_sorted[reference_index]
        else:
            value = comparison_sorted[comparison_index]
        while reference_index < total_reference and reference_sorted[reference_index] <= value:
            reference_index += 1
        while comparison_index < total_comparison and comparison_sorted[comparison_index] <= value:
            comparison_index += 1
        reference_cdf = reference_index / total_reference
        comparison_cdf = comparison_index / total_comparison
        distance = max(distance, abs(reference_cdf - comparison_cdf))
    return distance


def _series_result(
    source_id: str,
    reference: list[float],
    comparison: list[float],
    config: DomainShiftConfig,
) -> DomainShiftSeries:
    reference_mean = _mean(reference)
    comparison_mean = _mean(comparison)
    reference_std = _std(reference)
    comparison_std = _std(comparison)
    scale = max(reference_std, 1e-12)
    standardized_mean_shift = abs(comparison_mean - reference_mean) / scale
    if reference_std <= 1e-12 and comparison_std <= 1e-12:
        std_ratio = 1.0
    elif reference_std <= 1e-12:
        std_ratio = float("inf")
    else:
        std_ratio = max(
            comparison_std / reference_std,
            reference_std / max(comparison_std, 1e-12),
        )
    psi = _psi(reference, comparison, config.histogram_bins)
    cdf_distance = _empirical_cdf_distance(reference, comparison)

    reasons: list[str] = []
    if psi >= config.psi_threshold:
        reasons.append("population_stability_index")
    if cdf_distance >= config.cdf_distance_threshold:
        reasons.append("empirical_cdf_distance")
    if standardized_mean_shift >= config.standardized_mean_threshold:
        reasons.append("standardized_mean_shift")
    if std_ratio >= config.std_ratio_threshold:
        reasons.append("std_ratio")

    score_components = [
        min(1.0, psi / config.psi_threshold),
        min(1.0, cdf_distance / config.cdf_distance_threshold),
        min(1.0, standardized_mean_shift / config.standardized_mean_threshold),
        min(1.0, (std_ratio - 1.0) / (config.std_ratio_threshold - 1.0)),
    ]
    shift_score = max(score_components)
    payload = {
        "source_id": source_id,
        "reference_samples": len(reference),
        "comparison_samples": len(comparison),
        "reference_mean": reference_mean,
        "comparison_mean": comparison_mean,
        "reference_std": reference_std,
        "comparison_std": comparison_std,
        "standardized_mean_shift": standardized_mean_shift,
        "std_ratio": std_ratio,
        "population_stability_index": psi,
        "empirical_cdf_distance": cdf_distance,
        "shift_score": shift_score,
        "shift_detected": bool(reasons),
        "detection_reasons": reasons,
    }
    return DomainShiftSeries(
        source_id=source_id,
        reference_samples=len(reference),
        comparison_samples=len(comparison),
        reference_mean=reference_mean,
        comparison_mean=comparison_mean,
        reference_std=reference_std,
        comparison_std=comparison_std,
        standardized_mean_shift=standardized_mean_shift,
        std_ratio=std_ratio,
        population_stability_index=psi,
        empirical_cdf_distance=cdf_distance,
        shift_score=shift_score,
        shift_detected=bool(reasons),
        detection_reasons=tuple(reasons),
        series_fingerprint=_fingerprint(payload),
    )


class RealDomainShiftRunner:
    """Detect chronological telemetry distribution shift without label leakage."""

    def run(
        self,
        path: Path,
        *,
        config: DomainShiftConfig | None = None,
        evidence_class: DomainShiftEvidence = DomainShiftEvidence.PUBLIC_DATA,
    ) -> DomainShiftReport:
        effective = config or DomainShiftConfig()
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
        if evidence_class is DomainShiftEvidence.PUBLIC_DATA and not provenance_verified:
            raise ValueError(
                "public-data domain-shift detection requires a verified provenance manifest"
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

        results: list[DomainShiftSeries] = []
        aggregate_reference = 0
        aggregate_comparison = 0
        weighted_scores: list[tuple[float, int]] = []

        for source_id in sorted(grouped):
            ordered = sorted(grouped[source_id], key=lambda item: (item[0], item[2]))
            if len(ordered) > effective.max_rows_per_series:
                ordered = ordered[-effective.max_rows_per_series:]
            fit_rows, _, test_rows = _split_series(ordered, effective)
            if len(test_rows) < effective.minimum_comparison_samples:
                continue
            reference_values = [item[1] for item in fit_rows]
            comparison_values = [item[1] for item in test_rows]
            result = _series_result(
                source_id,
                reference_values,
                comparison_values,
                effective,
            )
            results.append(result)
            aggregate_reference += len(reference_values)
            aggregate_comparison += len(comparison_values)
            weighted_scores.append((result.shift_score, len(comparison_values)))

        if not results:
            raise ValueError("no eligible real telemetry series for domain-shift detection")

        total_weight = sum(weight for _, weight in weighted_scores)
        aggregate_mean_score = (
            sum(score * weight for score, weight in weighted_scores) / total_weight
        )
        aggregate_max_score = max(result.shift_score for result in results)
        shifted_count = sum(result.shift_detected for result in results)
        payload = {
            "dataset_path": path.as_posix(),
            "source_sha256": source_sha256,
            "row_count": row_count,
            "config": effective.model_dump(mode="json"),
            "series_results": [result.model_dump(mode="json") for result in results],
            "aggregate_reference_samples": aggregate_reference,
            "aggregate_comparison_samples": aggregate_comparison,
        }
        return DomainShiftReport(
            status="pass",
            evidence_class=evidence_class,
            dataset_path=path.as_posix(),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            row_count=row_count,
            series_count=len(grouped),
            analyzed_series_count=len(results),
            shifted_series_count=shifted_count,
            aggregate_reference_samples=aggregate_reference,
            aggregate_comparison_samples=aggregate_comparison,
            aggregate_mean_shift_score=aggregate_mean_score,
            aggregate_max_shift_score=aggregate_max_score,
            shift_rate=shifted_count / len(results),
            series_results=tuple(results),
            detection_fingerprint=_fingerprint(payload),
            network_mutation=False,
        )
