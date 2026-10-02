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


def _definition() -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="phase53-fixture",
        hypothesis="integrated research execution remains deterministic",
        seed=7,
        variants=(
            ExperimentVariant(variant_id="baseline", factors=(ExperimentFactor(name="policy", value="base"),), replicate_count=2),
            ExperimentVariant(variant_id="treatment", factors=(ExperimentFactor(name="policy", value="adaptive"),), replicate_count=2),
        ),
        metrics=(ExperimentMetricSpec(name="throughput", direction=ExperimentMetricDirection.HIGHER_IS_BETTER),),
        fixture="synthetic offline research fixture",
    )


def _evaluator(variant: str, seed: int, factors: Mapping[str, str]) -> Mapping[str, float]:
    return {"throughput": 80.0 if variant == "treatment" else 70.0}


def _stress() -> tuple[StressScenario, ...]:
    return (
        StressScenario(
            scenario_id="packet-loss",
            failure_mode=FailureMode.PACKET_LOSS,
            baseline_value=0.01,
            stressed_value=0.30,
            recovered_value=0.01,
            warning_threshold=0.10,
            critical_threshold=0.25,
            higher_is_worse=True,
            expected_severity=FailureSeverity.CRITICAL,
        ),
    )


def _platform() -> AutonomousSAGResearchPlatform:
    return AutonomousSAGResearchPlatform(
        (
            ResearchComponent(component_id="experiments", stage=ResearchStage.EXPERIMENT, capability="controlled experiments"),
            ResearchComponent(component_id="reproducibility", stage=ResearchStage.REPRODUCIBILITY, capability="deterministic provenance"),
            ResearchComponent(component_id="stress", stage=ResearchStage.STRESS, capability="failure campaigns"),
        )
    )


def test_integrated_run_is_deterministic() -> None:
    first, result = _platform().run(
        run_id="phase53-run",
        experiment=_definition(),
        evaluator=_evaluator,
        stress_scenarios=_stress(),
        fixture="synthetic offline research fixture",
    )
    second, _ = _platform().run(
        run_id="phase53-run",
        experiment=_definition(),
        evaluator=_evaluator,
        stress_scenarios=_stress(),
        fixture="synthetic offline research fixture",
    )
    assert first.platform_fingerprint == second.platform_fingerprint
    assert first.experiment_fingerprint == result.result_fingerprint
    assert first.network_mutation is False
    assert first.stages_completed == (ResearchStage.EXPERIMENT, ResearchStage.STRESS, ResearchStage.REPRODUCIBILITY)


def test_components_are_sorted_and_unique() -> None:
    platform = _platform()
    assert tuple(item.component_id for item in platform.components) == ("experiments", "reproducibility", "stress")


def test_duplicate_component_is_rejected() -> None:
    try:
        AutonomousSAGResearchPlatform(
            (
                ResearchComponent(component_id="x", stage=ResearchStage.EXPERIMENT, capability="a"),
                ResearchComponent(component_id="x", stage=ResearchStage.STRESS, capability="b"),
            )
        )
    except ValueError as exc:
        assert "identifiers must be unique" in str(exc)
    else:
        raise AssertionError("duplicate component should fail")


def test_required_stages_are_enforced() -> None:
    platform = AutonomousSAGResearchPlatform(
        (ResearchComponent(component_id="experiment", stage=ResearchStage.EXPERIMENT, capability="experiment"),)
    )
    try:
        platform.run(
            run_id="phase53-run",
            experiment=_definition(),
            evaluator=_evaluator,
            stress_scenarios=_stress(),
            fixture="synthetic offline research fixture",
        )
    except ValueError as exc:
        assert "requires experiment and stress stages" in str(exc)
    else:
        raise AssertionError("missing stress stage should fail")
