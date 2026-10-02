from __future__ import annotations

from collections.abc import Iterable

from sag_network.predictive.models import (
    ForecastSeries,
    PredictiveEarlyWarning,
    PredictiveThresholdRule,
    WarningSeverity,
)


def _severity(lead_time_s: float, rule: PredictiveThresholdRule) -> WarningSeverity:
    if lead_time_s <= rule.critical_within_s:
        return WarningSeverity.CRITICAL
    if lead_time_s <= rule.warning_within_s:
        return WarningSeverity.WARNING
    return WarningSeverity.WATCH


def evaluate_early_warnings(
    forecasts: Iterable[ForecastSeries],
    *,
    reference_time_s: float,
    rules: Iterable[PredictiveThresholdRule],
) -> list[PredictiveEarlyWarning]:
    """Detect future threshold crossings without changing the underlying network state."""
    rule_list = list(rules)
    warnings: list[PredictiveEarlyWarning] = []
    for series in forecasts:
        if series.feature_vector is None or not series.points:
            continue
        applicable = [
            rule
            for rule in rule_list
            if rule.metric is series.metric and (rule.source_id is None or rule.source_id == series.source_id)
        ]
        for rule in applicable:
            crossing: tuple[float, float, float, str] | None = None
            for point in series.points:
                if point.confidence_score < rule.minimum_confidence:
                    continue
                if rule.minimum_value is not None and point.predicted_value < rule.minimum_value:
                    crossing = (
                        point.forecast_timestamp_s,
                        point.predicted_value,
                        rule.minimum_value,
                        "below_minimum",
                    )
                    break
                if rule.maximum_value is not None and point.predicted_value > rule.maximum_value:
                    crossing = (
                        point.forecast_timestamp_s,
                        point.predicted_value,
                        rule.maximum_value,
                        "above_maximum",
                    )
                    break
            if crossing is None:
                continue
            forecast_timestamp, predicted_value, threshold_value, direction = crossing
            lead_time = max(0.0, forecast_timestamp - reference_time_s)
            severity = _severity(lead_time, rule)
            confidence = next(
                point.confidence_score
                for point in series.points
                if point.forecast_timestamp_s == forecast_timestamp
            )
            warnings.append(
                PredictiveEarlyWarning(
                    source_id=series.source_id,
                    domain=series.domain,
                    metric=series.metric,
                    severity=severity,
                    forecast_timestamp_s=forecast_timestamp,
                    lead_time_s=lead_time,
                    predicted_value=predicted_value,
                    threshold_value=threshold_value,
                    threshold_direction=direction,
                    confidence_score=confidence,
                    reason=(
                        f"predicted {series.metric.value} {direction.replace('_', ' ')} "
                        f"threshold within {lead_time:.3f}s"
                    ),
                )
            )
    return sorted(
        warnings,
        key=lambda warning: (
            warning.forecast_timestamp_s,
            warning.source_id,
            warning.metric.value,
            warning.severity.value,
        ),
    )
