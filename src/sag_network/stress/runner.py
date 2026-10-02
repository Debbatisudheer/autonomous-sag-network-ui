from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from sag_network.stress.models import (
    FailureSeverity,
    StressCampaignResult,
    StressFinding,
    StressScenario,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class StressFailureCampaign:
    """Run deterministic failure injections without mutating production state."""

    def run(
        self,
        scenarios: Iterable[StressScenario],
        *,
        campaign_id: str,
        fixture: str,
    ) -> StressCampaignResult:
        ordered = sorted(scenarios, key=lambda item: item.scenario_id)
        if not ordered:
            raise ValueError("stress campaign requires at least one scenario")
        if len({item.scenario_id for item in ordered}) != len(ordered):
            raise ValueError("stress campaign scenario identifiers must be unique")

        findings: list[StressFinding] = []
        for scenario in ordered:
            if (
                scenario.higher_is_worse
                and scenario.warning_threshold > scenario.critical_threshold
            ):
                raise ValueError("warning threshold cannot exceed critical threshold")
            if (
                not scenario.higher_is_worse
                and scenario.warning_threshold < scenario.critical_threshold
            ):
                raise ValueError("warning threshold cannot be below critical threshold")
            recovery_error = abs(scenario.recovered_value - scenario.baseline_value)
            if recovery_error > scenario.recovery_tolerance:
                raise ValueError(f"scenario {scenario.scenario_id} did not recover within tolerance")
            severity, threshold_breached = self._classify(scenario)
            if severity is not scenario.expected_severity:
                raise ValueError(
                    f"scenario {scenario.scenario_id} produced {severity.value}, "
                    f"expected {scenario.expected_severity.value}"
                )
            absolute_delta = scenario.stressed_value - scenario.baseline_value
            relative_delta = (
                None
                if scenario.baseline_value == 0.0
                else absolute_delta / abs(scenario.baseline_value)
            )
            findings.append(
                StressFinding(
                    scenario_id=scenario.scenario_id,
                    failure_mode=scenario.failure_mode,
                    baseline_value=scenario.baseline_value,
                    stressed_value=scenario.stressed_value,
                    absolute_delta=absolute_delta,
                    relative_delta=relative_delta,
                    recovery_error=recovery_error,
                    severity=severity,
                    threshold_breached=threshold_breached,
                    recovery_observed=True,
                )
            )

        payload = {
            "campaign_id": campaign_id,
            "findings": [item.model_dump(mode="json") for item in findings],
            "fixture": fixture,
        }
        return StressCampaignResult(
            campaign_id=campaign_id,
            scenario_count=len(ordered),
            finding_count=len(findings),
            critical_count=sum(item.severity is FailureSeverity.CRITICAL for item in findings),
            warning_count=sum(item.severity is FailureSeverity.WARNING for item in findings),
            passed_count=sum(item.severity is FailureSeverity.NONE for item in findings),
            findings=tuple(findings),
            campaign_fingerprint=_fingerprint(payload),
            fixture=fixture,
        )

    @staticmethod
    def _classify(scenario: StressScenario) -> tuple[FailureSeverity, bool]:
        value = scenario.stressed_value
        if scenario.higher_is_worse:
            if value >= scenario.critical_threshold:
                return FailureSeverity.CRITICAL, True
            if value >= scenario.warning_threshold:
                return FailureSeverity.WARNING, True
        else:
            if value <= scenario.critical_threshold:
                return FailureSeverity.CRITICAL, True
            if value <= scenario.warning_threshold:
                return FailureSeverity.WARNING, True
        return FailureSeverity.NONE, False
