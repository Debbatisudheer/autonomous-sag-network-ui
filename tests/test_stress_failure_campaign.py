from __future__ import annotations

import pytest

from sag_network.stress import FailureMode, FailureSeverity, StressFailureCampaign, StressScenario


def scenario(
    scenario_id: str = "s1",
    *,
    stressed: float = 0.9,
    recovered: float = 0.6,
    warning: float = 0.8,
    critical: float = 0.95,
    higher_is_worse: bool = True,
    expected: FailureSeverity = FailureSeverity.WARNING,
) -> StressScenario:
    return StressScenario(
        scenario_id=scenario_id,
        failure_mode=FailureMode.RESOURCE_OVERLOAD,
        baseline_value=0.6,
        stressed_value=stressed,
        recovered_value=recovered,
        warning_threshold=warning,
        critical_threshold=critical,
        higher_is_worse=higher_is_worse,
        expected_severity=expected,
    )


def test_campaign_is_deterministic_and_orders_scenarios() -> None:
    runner = StressFailureCampaign()
    scenarios = [
        scenario("b", stressed=0.6, expected=FailureSeverity.NONE),
        scenario("a"),
    ]
    first = runner.run(scenarios, campaign_id="c", fixture="fixture")
    second = runner.run(reversed(scenarios), campaign_id="c", fixture="fixture")

    assert first == second
    assert [item.scenario_id for item in first.findings] == ["a", "b"]
    assert first.warning_count == 1
    assert first.passed_count == 1
    assert all(item.recovery_observed for item in first.findings)


def test_lower_is_worse_classification() -> None:
    result = StressFailureCampaign().run(
        [
            scenario(
                stressed=0.0,
                warning=0.5,
                critical=0.1,
                higher_is_worse=False,
                expected=FailureSeverity.CRITICAL,
            )
        ],
        campaign_id="c",
        fixture="fixture",
    )
    assert result.critical_count == 1
    assert result.findings[0].threshold_breached is True
    assert result.findings[0].recovery_observed is True
    assert result.findings[0].recovery_error == 0.0


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="identifiers must be unique"):
        StressFailureCampaign().run(
            [scenario("same"), scenario("same", stressed=0.6, expected=FailureSeverity.NONE)],
            campaign_id="c",
            fixture="fixture",
        )


def test_invalid_threshold_order_is_rejected() -> None:
    with pytest.raises(ValueError, match="warning threshold cannot exceed"):
        StressFailureCampaign().run(
            [scenario(warning=0.9, critical=0.8)],
            campaign_id="c",
            fixture="fixture",
        )


def test_recovery_outside_tolerance_is_rejected() -> None:
    with pytest.raises(ValueError, match="did not recover within tolerance"):
        StressFailureCampaign().run(
            [scenario(recovered=0.7)],
            campaign_id="c",
            fixture="fixture",
        )


def test_empty_campaign_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one scenario"):
        StressFailureCampaign().run([], campaign_id="c", fixture="fixture")
