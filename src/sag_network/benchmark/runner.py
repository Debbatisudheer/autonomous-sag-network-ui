from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from sag_network.benchmark.models import BenchmarkResult, BenchmarkScenario


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FinalBenchmarkRunner:
    """Run a deterministic, offline benchmark over the validated SAG research platform."""

    def run(
        self,
        scenarios: Iterable[BenchmarkScenario],
        *,
        benchmark_id: str,
        fixture: str,
    ) -> BenchmarkResult:
        if not benchmark_id:
            raise ValueError("benchmark identifier must not be empty")

        ordered = tuple(sorted(scenarios, key=lambda item: item.scenario_id))

        if not ordered:
            raise ValueError("final benchmark requires at least one scenario")

        if len({item.scenario_id for item in ordered}) != len(ordered):
            raise ValueError("benchmark scenario identifiers must be unique")

        total_metrics = sum(len(item.metrics) for item in ordered)
        target_metrics = sum(
            sum(metric.target_met for metric in item.metrics)
            for item in ordered
        )
        passed = sum(
            all(metric.target_met for metric in item.metrics)
            for item in ordered
        )

        payload = {
            "benchmark_id": benchmark_id,
            "fixture": fixture,
            "scenarios": [item.model_dump(mode="json") for item in ordered],
        }

        fingerprint = _fingerprint(payload)

        return BenchmarkResult(
            benchmark_id=benchmark_id,
            scenario_count=len(ordered),
            metric_count=total_metrics,
            scenarios_passed=passed,
            metric_targets_met=target_metrics,
            total_metrics=total_metrics,
            pass_rate=passed / len(ordered),
            benchmark_fingerprint=fingerprint,
            deterministic=True,
            network_mutation=False,
            fixture=fixture,
        )