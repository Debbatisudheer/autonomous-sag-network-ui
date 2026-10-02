from __future__ import annotations

import json

from sag_network.experiments import (
    ControlledExperimentRunner,
    ExperimentDefinition,
    ExperimentFactor,
    ExperimentMetricDirection,
    ExperimentMetricSpec,
    ExperimentVariant,
)


def evaluate(variant_id: str, seed: int, factors: dict[str, str]) -> dict[str, float]:
    load = float(factors["load"])
    efficiency = 0.92 if variant_id == "treatment" else 0.84
    latency = 4.0 + load * 0.25 + seed * 0.0
    return {"throughput": 100.0 * efficiency - load, "latency_ms": latency}


def main() -> None:
    definition = ExperimentDefinition(
        experiment_id="phase49-wireless-policy",
        hypothesis="The treatment policy improves throughput without increasing latency.",
        seed=4900,
        variants=(
            ExperimentVariant(
                variant_id="baseline",
                factors=(ExperimentFactor(name="load", value="10"),),
                replicate_count=3,
            ),
            ExperimentVariant(
                variant_id="treatment",
                factors=(ExperimentFactor(name="load", value="10"),),
                replicate_count=3,
            ),
        ),
        metrics=(
            ExperimentMetricSpec(
                name="throughput", direction=ExperimentMetricDirection.HIGHER_IS_BETTER
            ),
            ExperimentMetricSpec(
                name="latency_ms", direction=ExperimentMetricDirection.LOWER_IS_BETTER
            ),
        ),
        fixture="synthetic offline controlled-experiment fixture",
    )
    result = ControlledExperimentRunner().run(definition, evaluate)
    print(
        json.dumps(
            {
                "name": "Controlled Experiments",
                "phase": "49",
                "status": "pass",
                "experiment_id": result.experiment_id,
                "variant_count": len(definition.variants),
                "metric_count": len(definition.metrics),
                "replicate_count": definition.variants[0].replicate_count,
                "comparison_count": len(result.comparisons),
                "comparisons": [item.model_dump(mode="json") for item in result.comparisons],
                "result_fingerprint": result.result_fingerprint,
                "network_mutation": False,
                "fixture": result.fixture,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
