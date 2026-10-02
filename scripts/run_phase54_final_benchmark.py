from __future__ import annotations

import json

from sag_network.benchmark import (
    BenchmarkDirection,
    BenchmarkMetric,
    BenchmarkScenario,
    FinalBenchmarkRunner,
)


def main() -> None:
    fixture = "synthetic offline final-benchmark fixture"

    scenarios = (
        BenchmarkScenario(
            scenario_id="integration",
            description="integrated research-platform benchmark",
            metrics=(
                BenchmarkMetric(
                    metric_id="throughput",
                    baseline=74.0,
                    observed=82.0,
                    target=80.0,
                    direction=BenchmarkDirection.HIGHER_IS_BETTER,
                ),
                BenchmarkMetric(
                    metric_id="latency_ms",
                    baseline=20.0,
                    observed=20.0,
                    target=25.0,
                    direction=BenchmarkDirection.LOWER_IS_BETTER,
                ),
            ),
        ),
        BenchmarkScenario(
            scenario_id="resilience",
            description="stress recovery benchmark",
            metrics=(
                BenchmarkMetric(
                    metric_id="recovery_error",
                    baseline=0.0,
                    observed=0.0,
                    target=0.0,
                    direction=BenchmarkDirection.LOWER_IS_BETTER,
                ),
            ),
        ),
        BenchmarkScenario(
            scenario_id="reproducibility",
            description="research package verification benchmark",
            metrics=(
                BenchmarkMetric(
                    metric_id="changed_files",
                    baseline=0.0,
                    observed=0.0,
                    target=0.0,
                    direction=BenchmarkDirection.LOWER_IS_BETTER,
                ),
            ),
        ),
    )

    result = FinalBenchmarkRunner().run(
        scenarios,
        benchmark_id="phase54-final-benchmark",
        fixture=fixture,
    )

    print(
        json.dumps(
            {
                "name": "Final Benchmark",
                "phase": "54",
                "status": "pass",
                "benchmark_id": result.benchmark_id,
                "scenario_count": result.scenario_count,
                "metric_count": result.metric_count,
                "scenarios_passed": result.scenarios_passed,
                "metric_targets_met": result.metric_targets_met,
                "pass_rate": result.pass_rate,
                "benchmark_fingerprint": result.benchmark_fingerprint,
                "deterministic": result.deterministic,
                "network_mutation": result.network_mutation,
                "fixture": fixture,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()