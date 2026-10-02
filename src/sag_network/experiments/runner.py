from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping

from sag_network.experiments.models import (
    ExperimentComparison,
    ExperimentDefinition,
    ExperimentMetricResult,
    ExperimentResult,
)

MetricEvaluator = Callable[[str, int, Mapping[str, str]], Mapping[str, float]]


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _mean(samples: tuple[float, ...]) -> float:
    return sum(samples) / len(samples)


class ControlledExperimentRunner:
    """Run deterministic multi-variant experiments without mutating network state."""

    def run(
        self,
        definition: ExperimentDefinition,
        evaluator: MetricEvaluator,
    ) -> ExperimentResult:
        metric_results: list[ExperimentMetricResult] = []
        for variant in definition.variants:
            factor_values = {factor.name: factor.value for factor in variant.factors}
            if len(factor_values) != len(variant.factors):
                raise ValueError("factor names must be unique within a variant")
            for replicate in range(variant.replicate_count):
                values = evaluator(variant.variant_id, definition.seed + replicate, factor_values)
                missing = {
                    metric.name for metric in definition.metrics if metric.name not in values
                }
                if missing:
                    raise ValueError(
                        f"evaluator omitted metrics: {', '.join(sorted(missing))}"
                    )
                for metric in definition.metrics:
                    existing = next(
                        (
                            result
                            for result in metric_results
                            if result.metric_name == metric.name
                            and result.variant_id == variant.variant_id
                        ),
                        None,
                    )
                    samples = tuple(existing.samples) if existing else ()
                    metric_results = [
                        result
                        for result in metric_results
                        if not (
                            result.metric_name == metric.name
                            and result.variant_id == variant.variant_id
                        )
                    ]
                    updated_samples = (*samples, float(values[metric.name]))
                    metric_results.append(
                        ExperimentMetricResult(
                            metric_name=metric.name,
                            variant_id=variant.variant_id,
                            samples=updated_samples,
                            mean=_mean(updated_samples),
                        )
                    )

        baseline = definition.variants[0].variant_id
        treatment = definition.variants[1].variant_id
        comparisons: list[ExperimentComparison] = []
        for metric in definition.metrics:
            baseline_result = self._metric_result(metric_results, metric.name, baseline)
            treatment_result = self._metric_result(metric_results, metric.name, treatment)
            absolute_delta = treatment_result.mean - baseline_result.mean
            relative_delta = (
                None
                if baseline_result.mean == 0
                else absolute_delta / abs(baseline_result.mean)
            )
            if metric.direction.value == "higher_is_better":
                improved = absolute_delta > 0
            else:
                improved = absolute_delta < 0
            comparisons.append(
                ExperimentComparison(
                    metric_name=metric.name,
                    baseline_variant_id=baseline,
                    treatment_variant_id=treatment,
                    baseline_mean=baseline_result.mean,
                    treatment_mean=treatment_result.mean,
                    absolute_delta=absolute_delta,
                    relative_delta=relative_delta,
                    direction=metric.direction,
                    treatment_improved=improved,
                )
            )

        payload = {
            "experiment_id": definition.experiment_id,
            "seed": definition.seed,
            "metric_results": [item.model_dump(mode="json") for item in metric_results],
            "comparisons": [item.model_dump(mode="json") for item in comparisons],
        }
        return ExperimentResult(
            experiment_id=definition.experiment_id,
            seed=definition.seed,
            metric_results=tuple(
                sorted(metric_results, key=lambda item: (item.metric_name, item.variant_id))
            ),
            comparisons=tuple(sorted(comparisons, key=lambda item: item.metric_name)),
            result_fingerprint=_fingerprint(payload),
            fixture=definition.fixture,
        )

    @staticmethod
    def _metric_result(
        results: list[ExperimentMetricResult],
        metric_name: str,
        variant_id: str,
    ) -> ExperimentMetricResult:
        for result in results:
            if result.metric_name == metric_name and result.variant_id == variant_id:
                return result
        raise ValueError(f"missing metric result: {metric_name}/{variant_id}")
