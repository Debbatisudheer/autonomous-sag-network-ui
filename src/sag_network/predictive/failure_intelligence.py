from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sag_network.predictive.failure_models import (
    FailureDirection,
    FailureIntelligenceReport,
    FailureIntelligenceSeries,
    FailureRiskLevel,
    FailureThresholdRule,
    PredictedFailure,
)
from sag_network.predictive.uncertainty_models import (
    UncertaintyInterval,
    UncertaintyReport,
    UncertaintySeries,
)


def _event_id(
    source_id: str,
    metric: str,
    direction: str,
    timestamp_s: float,
    threshold: float,
) -> str:
    payload = f"{source_id}|{metric}|{direction}|{timestamp_s:.9f}|{threshold:.9f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _risk_level(
    lead_time_s: float,
    rule: FailureThresholdRule,
) -> FailureRiskLevel:
    if lead_time_s <= rule.critical_within_s:
        return FailureRiskLevel.CRITICAL
    if lead_time_s <= rule.warning_within_s:
        return FailureRiskLevel.WARNING
    return FailureRiskLevel.WATCH


def _score(
    distance: float,
    margin: float,
    uncertainty_score: float,
) -> float:
    if margin <= 0:
        return 1.0
    proximity = max(0.0, min(1.0, 1.0 - distance / margin))
    return max(0.0, min(1.0, 0.7 * proximity + 0.3 * uncertainty_score))


def _finding(
    series: UncertaintySeries,
    interval: UncertaintyInterval,
    threshold: float,
    direction: FailureDirection,
    rule: FailureThresholdRule,
    reference_time_s: float,
) -> PredictedFailure:
    forecast_timestamp = interval.forecast_timestamp_s
    lead_time = max(0.0, forecast_timestamp - reference_time_s)

    if direction is FailureDirection.BELOW_MINIMUM:
        distance = max(0.0, interval.predicted_value - threshold)
        margin = (
            max(interval.interval_width / 2.0, 1e-9)
            * max(rule.uncertainty_buffer_multiplier, 1.0)
        )
    else:
        distance = max(0.0, threshold - interval.predicted_value)
        margin = (
            max(interval.interval_width / 2.0, 1e-9)
            * max(rule.uncertainty_buffer_multiplier, 1.0)
        )

    return PredictedFailure(
        event_id=_event_id(
            series.source_id,
            series.metric.value,
            direction.value,
            forecast_timestamp,
            threshold,
        ),
        source_id=series.source_id,
        domain=series.domain,
        metric=series.metric,
        direction=direction,
        risk_level=_risk_level(lead_time, rule),
        forecast_timestamp_s=forecast_timestamp,
        lead_time_s=lead_time,
        predicted_value=interval.predicted_value,
        threshold_value=threshold,
        lower_bound=interval.lower_bound,
        upper_bound=interval.upper_bound,
        risk_score=_score(
            distance,
            margin,
            interval.uncertainty_score,
        ),
        uncertainty_score=interval.uncertainty_score,
        reason=(
            f"forecast interval crosses {direction.value.replace('_', ' ')} "
            f"threshold {threshold:g} within {lead_time:.3f}s"
        ),
    )


def _series_findings(
    series: UncertaintySeries,
    rules: list[FailureThresholdRule],
    reference_time_s: float,
) -> list[PredictedFailure]:
    findings: list[PredictedFailure] = []
    applicable = [
        rule
        for rule in rules
        if rule.metric is series.metric
        and (rule.source_id is None or rule.source_id == series.source_id)
    ]

    for rule in applicable:
        for interval in series.intervals:
            if (
                rule.minimum_value is not None
                and interval.lower_bound <= rule.minimum_value
            ):
                findings.append(
                    _finding(
                        series,
                        interval,
                        rule.minimum_value,
                        FailureDirection.BELOW_MINIMUM,
                        rule,
                        reference_time_s,
                    )
                )

            if (
                rule.maximum_value is not None
                and interval.upper_bound >= rule.maximum_value
            ):
                findings.append(
                    _finding(
                        series,
                        interval,
                        rule.maximum_value,
                        FailureDirection.ABOVE_MAXIMUM,
                        rule,
                        reference_time_s,
                    )
                )

    return sorted(
        findings,
        key=lambda item: (
            item.forecast_timestamp_s,
            item.source_id,
            item.metric.value,
            item.direction.value,
            item.event_id,
        ),
    )


class PredictiveFailureIntelligence:
    """Turn calibrated forecast intervals into explicit, deterministic failure-risk findings."""

    def analyze(
        self,
        uncertainty_report: UncertaintyReport,
        *,
        reference_time_s: float,
        rules: Iterable[FailureThresholdRule],
    ) -> FailureIntelligenceReport:
        rule_list = sorted(
            rules,
            key=lambda item: (
                item.source_id or "",
                item.metric.value,
                (
                    item.minimum_value
                    if item.minimum_value is not None
                    else float("inf")
                ),
                (
                    item.maximum_value
                    if item.maximum_value is not None
                    else float("inf")
                ),
            ),
        )

        series_results = [
            FailureIntelligenceSeries(
                source_id=series.source_id,
                domain=series.domain,
                metric=series.metric,
                predicted_failures=_series_findings(
                    series,
                    rule_list,
                    reference_time_s,
                ),
            )
            for series in sorted(
                uncertainty_report.series,
                key=lambda item: (item.source_id, item.metric.value),
            )
        ]

        return FailureIntelligenceReport(
            timestamp_s=reference_time_s,
            rules=rule_list,
            series=series_results,
        )
