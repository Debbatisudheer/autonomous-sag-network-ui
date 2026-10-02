from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping

from sag_network.experiments import (
    ControlledExperimentRunner,
    ExperimentDefinition,
    ExperimentResult,
)
from sag_network.research.models import ResearchComponent, ResearchRunResult, ResearchStage
from sag_network.stress import StressFailureCampaign, StressScenario

MetricEvaluator = Callable[[str, int, Mapping[str, str]], Mapping[str, float]]


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AutonomousSAGResearchPlatform:
    """Integrate deterministic experiments and failure campaigns into one research run."""

    def __init__(self, components: Iterable[ResearchComponent]) -> None:
        ordered = tuple(sorted(components, key=lambda item: item.component_id))
        if not ordered:
            raise ValueError("research platform requires at least one component")
        if len({item.component_id for item in ordered}) != len(ordered):
            raise ValueError("research component identifiers must be unique")
        self._components = ordered

    @property
    def components(self) -> tuple[ResearchComponent, ...]:
        """Return the immutable component registry."""
        return self._components

    def run(
        self,
        *,
        run_id: str,
        experiment: ExperimentDefinition,
        evaluator: MetricEvaluator,
        stress_scenarios: Iterable[StressScenario],
        fixture: str,
    ) -> tuple[ResearchRunResult, ExperimentResult]:
        if not run_id:
            raise ValueError("research run identifier must not be empty")
        experiment_result = ControlledExperimentRunner().run(experiment, evaluator)
        stress_result = StressFailureCampaign().run(
            stress_scenarios,
            campaign_id=f"{run_id}-stress",
            fixture=fixture,
        )
        stages = tuple(stage for stage in ResearchStage if any(item.stage is stage for item in self._components))
        if ResearchStage.EXPERIMENT not in stages or ResearchStage.STRESS not in stages:
            raise ValueError("research platform requires experiment and stress stages")
        platform_payload = {
            "run_id": run_id,
            "components": [item.model_dump(mode="json") for item in self._components],
            "experiment_fingerprint": experiment_result.result_fingerprint,
            "stress_fingerprint": stress_result.campaign_fingerprint,
            "stages": [item.value for item in stages],
            "fixture": fixture,
        }
        result = ResearchRunResult(
            run_id=run_id,
            component_count=len(self._components),
            stages_completed=stages,
            experiment_fingerprint=experiment_result.result_fingerprint,
            stress_fingerprint=stress_result.campaign_fingerprint,
            platform_fingerprint=_fingerprint(platform_payload),
            network_mutation=False,
            fixture=fixture,
        )
        return result, experiment_result
