from sag_network.benchmark import (
    BenchmarkDirection,
    BenchmarkMetric,
    BenchmarkScenario,
    FinalBenchmarkRunner,
)


def _scenario() -> tuple[BenchmarkScenario, ...]:
    return (
        BenchmarkScenario(
            scenario_id="integration",
            description="validated research-platform integration",
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
            description="validated stress recovery",
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
            description="validated deterministic package verification",
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


def test_final_benchmark_is_deterministic() -> None:
    runner = FinalBenchmarkRunner()

    first = runner.run(
        _scenario(),
        benchmark_id="phase54-final-benchmark",
        fixture="synthetic offline final-benchmark fixture",
    )

    second = runner.run(
        _scenario(),
        benchmark_id="phase54-final-benchmark",
        fixture="synthetic offline final-benchmark fixture",
    )

    assert first == second
    assert first.scenarios_passed == 3
    assert first.metric_targets_met == 4
    assert first.total_metrics == 4
    assert first.pass_rate == 1.0
    assert first.network_mutation is False


def test_duplicate_scenario_is_rejected() -> None:
    scenario = _scenario()[0]
    duplicate = (scenario, scenario)

    try:
        FinalBenchmarkRunner().run(
            duplicate,
            benchmark_id="duplicate",
            fixture="fixture",
        )
    except ValueError as exc:
        assert "scenario identifiers" in str(exc)
    else:
        raise AssertionError("duplicate scenario identifiers must fail")