from __future__ import annotations

import pytest

from sag_network.experiments import (
    ControlledExperimentRunner,
    ExperimentDefinition,
    ExperimentFactor,
    ExperimentMetricDirection,
    ExperimentMetricSpec,
    ExperimentVariant,
)


def definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="test-exp",
        hypothesis="Treatment changes throughput.",
        seed=7,
        variants=(
            ExperimentVariant(
                variant_id="baseline",
                factors=(ExperimentFactor(name="mode", value="a"),),
                replicate_count=2,
            ),
            ExperimentVariant(
                variant_id="treatment",
                factors=(ExperimentFactor(name="mode", value="b"),),
                replicate_count=2,
            ),
        ),
        metrics=(
            ExperimentMetricSpec(
                name="throughput", direction=ExperimentMetricDirection.HIGHER_IS_BETTER
            ),
        ),
        fixture="synthetic test fixture",
    )


def evaluate(variant_id: str, seed: int, factors: dict[str, str]) -> dict[str, float]:
    del seed, factors
    return {"throughput": 10.0 if variant_id == "baseline" else 12.0}


def test_comparison_detects_improvement() -> None:
    result = ControlledExperimentRunner().run(definition(), evaluate)
    comparison = result.comparisons[0]
    assert comparison.absolute_delta == 2.0
    assert comparison.treatment_improved is True


def test_fingerprint_is_deterministic() -> None:
    first = ControlledExperimentRunner().run(definition(), evaluate)
    second = ControlledExperimentRunner().run(definition(), evaluate)
    assert first.result_fingerprint == second.result_fingerprint


def test_missing_metric_is_rejected() -> None:
    def incomplete(variant_id: str, seed: int, factors: dict[str, str]) -> dict[str, float]:
        del variant_id, seed, factors
        return {}

    with pytest.raises(ValueError, match="evaluator omitted metrics"):
        ControlledExperimentRunner().run(definition(), incomplete)


def test_duplicate_variants_are_rejected() -> None:
    with pytest.raises(ValueError, match="variant identifiers must be unique"):
        ExperimentDefinition(
            experiment_id="duplicate",
            hypothesis="test",
            seed=1,
            variants=(
                ExperimentVariant(
                    variant_id="same",
                    factors=(ExperimentFactor(name="mode", value="a"),),
                    replicate_count=1,
                ),
                ExperimentVariant(
                    variant_id="same",
                    factors=(ExperimentFactor(name="mode", value="b"),),
                    replicate_count=1,
                ),
            ),
            metrics=(
                ExperimentMetricSpec(
                    name="throughput",
                    direction=ExperimentMetricDirection.HIGHER_IS_BETTER,
                ),
            ),
            fixture="test",
        )
