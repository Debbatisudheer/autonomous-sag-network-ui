from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable

from sag_network.baseline_comparison.models import (
    BaselineComparison,
    BaselineComparisonConfig,
    BaselineComparisonResult,
    BaselineMethod,
    BaselineMetricResult,
)
from sag_network.predictive.ml_baseline import MLPredictiveBaseline
from sag_network.predictive.ml_models import MLBaselineConfig, MLBaselineStatus
from sag_network.telemetry.models import TelemetryRecord


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _errors(actuals: tuple[float, ...], predictions: tuple[float, ...]) -> tuple[float, float]:
    if len(actuals) != len(predictions) or not actuals:
        raise ValueError("actuals and predictions must have equal non-zero length")
    errors = [prediction - actual for actual, prediction in zip(actuals, predictions)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    return mae, rmse


class BaselineComparisonRunner:
    """Compare deterministic forecasting baselines on one temporal holdout."""

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        experiment_id: str,
        config: BaselineComparisonConfig | None = None,
        fixture: str,
    ) -> BaselineComparisonResult:
        effective_config = config or BaselineComparisonConfig()
        ordered = sorted(records, key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
        if not ordered:
            raise ValueError("baseline comparison requires telemetry records")
        keys = {(record.source_id, record.metric) for record in ordered}
        if len(keys) != 1:
            raise ValueError("baseline comparison requires exactly one source/metric series")
        if len(ordered) <= effective_config.holdout_size:
            raise ValueError("telemetry history is shorter than the configured holdout")

        training_count = len(ordered) - effective_config.holdout_size
        training = ordered[:training_count]
        holdout = ordered[training_count:]
        if len(training) < effective_config.minimum_training_samples:
            raise ValueError("telemetry history does not contain enough training samples")

        actuals = tuple(record.value for record in holdout)
        values = [record.value for record in training]
        persistence_predictions = tuple(values[-1] for _ in actuals)
        rolling_window = min(effective_config.rolling_window, len(values))
        rolling_value = sum(values[-rolling_window:]) / rolling_window
        rolling_predictions = tuple(rolling_value for _ in actuals)

        ml_config = MLBaselineConfig(
            lag_steps=effective_config.lag_steps,
            minimum_samples=max(4, training_count - effective_config.lag_steps),
            horizon_steps=effective_config.holdout_size,
            step_s=1.0,
        )
        ml_report = MLPredictiveBaseline(ml_config).train_and_forecast(
            training,
            reference_time_s=training[-1].timestamp_s,
        )
        series = ml_report.series[0]
        if series.status is not MLBaselineStatus.TRAINED or not series.forecasts:
            raise ValueError("ML predictive baseline could not train on the comparison set")
        ml_predictions = tuple(
            item.predicted_value
            for item in series.forecasts
            if item.predicted_value is not None
        )
        if len(ml_predictions) != len(actuals):
            raise ValueError("ML predictive baseline returned an incomplete holdout forecast")

        prediction_sets = (
            (BaselineMethod.PERSISTENCE, persistence_predictions),
            (BaselineMethod.ROLLING_MEAN, rolling_predictions),
            (BaselineMethod.ML_PREDICTIVE_BASELINE, ml_predictions),
        )
        metric_results: list[BaselineMetricResult] = []
        for method, predictions in prediction_sets:
            mae, rmse = _errors(actuals, predictions)
            metric_results.append(
                BaselineMetricResult(
                    method=method,
                    mean_absolute_error=mae,
                    root_mean_squared_error=rmse,
                    predictions=predictions,
                    actuals=actuals,
                )
            )

        reference = metric_results[0]
        comparisons: list[BaselineComparison] = []
        for result in metric_results[1:]:
            mae_delta = result.mean_absolute_error - reference.mean_absolute_error
            rmse_delta = result.root_mean_squared_error - reference.root_mean_squared_error
            comparisons.append(
                BaselineComparison(
                    reference_method=reference.method,
                    comparison_method=result.method,
                    mae_delta=mae_delta,
                    rmse_delta=rmse_delta,
                    relative_mae_delta=(
                        None
                        if reference.mean_absolute_error == 0.0
                        else mae_delta / abs(reference.mean_absolute_error)
                    ),
                    relative_rmse_delta=(
                        None
                        if reference.root_mean_squared_error == 0.0
                        else rmse_delta / abs(reference.root_mean_squared_error)
                    ),
                )
            )

        payload = {
            "experiment_id": experiment_id,
            "training_count": training_count,
            "holdout_count": len(holdout),
            "metric_results": [item.model_dump(mode="json") for item in metric_results],
            "comparisons": [item.model_dump(mode="json") for item in comparisons],
            "fixture": fixture,
        }
        return BaselineComparisonResult(
            experiment_id=experiment_id,
            training_count=training_count,
            holdout_count=len(holdout),
            metric_results=tuple(metric_results),
            comparisons=tuple(comparisons),
            result_fingerprint=_fingerprint(payload),
            fixture=fixture,
        )
