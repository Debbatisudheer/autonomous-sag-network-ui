from __future__ import annotations

import json
from collections.abc import Mapping

from sag_network.experiments import (
    ExperimentDefinition,
    ExperimentFactor,
    ExperimentMetricDirection,
    ExperimentMetricSpec,
    ExperimentVariant,
)
from sag_network.research import AutonomousSAGResearchPlatform, ResearchComponent, ResearchStage
from sag_network.stress import FailureMode, FailureSeverity, StressScenario


def main() -> None:
    fixture = "synthetic offline integrated research-platform fixture"
    platform = AutonomousSAGResearchPlatform(
        (
            ResearchComponent(component_id="experiments", stage=ResearchStage.EXPERIMENT, capability="controlled experiments"),
            ResearchComponent(component_id="reproducibility", stage=ResearchStage.REPRODUCIBILITY, capability="deterministic provenance"),
            ResearchComponent(component_id="stress", stage=ResearchStage.STRESS, capability="failure campaigns"),
        )
    )
    definition = ExperimentDefinition(
        experiment_id="phase53-integrated-study",
        hypothesis="adaptive policy improves throughput under a reproducible stress campaign",
        seed=53,
        variants=(
            ExperimentVariant(variant_id="baseline", factors=(ExperimentFactor(name="policy", value="baseline"),), replicate_count=3),
            ExperimentVariant(variant_id="adaptive", factors=(ExperimentFactor(name="policy", value="adaptive"),), replicate_count=3),
        ),
        metrics=(ExperimentMetricSpec(name="throughput", direction=ExperimentMetricDirection.HIGHER_IS_BETTER),),
        fixture=fixture,
    )

    def evaluator(variant: str, seed: int, factors: Mapping[str, str]) -> Mapping[str, float]:
        del seed, factors
        return {"throughput": 82.0 if variant == "adaptive" else 74.0}

    scenarios = (
        StressScenario(
            scenario_id="packet-loss-critical",
            failure_mode=FailureMode.PACKET_LOSS,
            baseline_value=0.01,
            stressed_value=0.35,
            recovered_value=0.01,
            warning_threshold=0.10,
            critical_threshold=0.25,
            higher_is_worse=True,
            expected_severity=FailureSeverity.CRITICAL,
        ),
        StressScenario(
            scenario_id="latency-warning",
            failure_mode=FailureMode.LATENCY_SPIKE,
            baseline_value=20.0,
            stressed_value=75.0,
            recovered_value=20.0,
            warning_threshold=50.0,
            critical_threshold=100.0,
            higher_is_worse=True,
            expected_severity=FailureSeverity.WARNING,
        ),
    )
    result, experiment_result = platform.run(
        run_id="phase53-autonomous-sag-research",
        experiment=definition,
        evaluator=evaluator,
        stress_scenarios=scenarios,
        fixture=fixture,
    )
    print(json.dumps({
        "name": "Autonomous SAG Research Platform",
        "phase": "53",
        "status": "pass",
        "run_id": result.run_id,
        "component_count": result.component_count,
        "stages_completed": [stage.value for stage in result.stages_completed],
        "experiment_fingerprint": result.experiment_fingerprint,
        "stress_fingerprint": result.stress_fingerprint,
        "platform_fingerprint": result.platform_fingerprint,
        "treatment_improved": experiment_result.comparisons[0].treatment_improved,
        "network_mutation": result.network_mutation,
        "fixture": fixture,
    }, indent=2))


if __name__ == "__main__":
    main()
