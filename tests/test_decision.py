from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.decision.engine import DecisionEngine
from sag_network.decision.models import DecisionActionType, DecisionConfig, DecisionStatus
from sag_network.domain.resource import ResourceUtilization
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.predictive.models import (
    PredictiveEarlyWarning,
    PredictiveReport,
    WarningSeverity,
)
from sag_network.resource.scheduler import SpectrumSchedulingSnapshot
from sag_network.telemetry.models import TelemetryMetric


def _candidate(
    resource_id: str,
    *,
    domain: NetworkDomain,
    margin: float,
    capacity: float,
    available: bool = True,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=domain,
        resource_type="test",
        available=available,
        distance_m=1000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=margin + 5.0,
        link_margin_db=margin,
        shannon_capacity_bps=capacity,
        estimated_capacity_bps=capacity,
        propagation_delay_ms=5.0,
        doppler_shift_hz=0.0,
    )


def _snapshot(*, timestamp_s: float = 10.0) -> UnifiedNetworkSnapshot:
    return UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=20_000_000.0,
                allocated_capacity_bps=20_000_000.0,
                candidates=[
                    _candidate("uav-a", domain=NetworkDomain.AIR, margin=1.5, capacity=50_000_000.0),
                    _candidate("gnd-a", domain=NetworkDomain.GROUND, margin=8.0, capacity=100_000_000.0),
                ],
            )
        ],
    )


def _warning(
    metric: TelemetryMetric = TelemetryMetric.SINR_DB,
    *,
    severity: WarningSeverity = WarningSeverity.CRITICAL,
) -> PredictiveEarlyWarning:
    return PredictiveEarlyWarning(
        source_id="uav-a:user-01",
        domain=NetworkDomain.AIR,
        metric=metric,
        severity=severity,
        forecast_timestamp_s=11.0,
        lead_time_s=1.0,
        predicted_value=8.0,
        threshold_value=10.0,
        threshold_direction="below_minimum",
        confidence_score=0.9,
        reason="predicted threshold violation",
    )


def _report(*warnings: PredictiveEarlyWarning, timestamp_s: float = 10.0) -> PredictiveReport:
    return PredictiveReport(timestamp_s=timestamp_s, early_warnings=list(warnings))


def test_selects_handover_for_predicted_radio_degradation() -> None:
    report = DecisionEngine().decide(_report(_warning()), network_snapshot=_snapshot())
    assert report.status is DecisionStatus.ACTION_SELECTED
    assert report.selected_decisions[0].action.action_type is DecisionActionType.PREPARE_HANDOVER
    assert report.selected_decisions[0].action.alternative_resource_id == "gnd-a"


def test_no_warning_produces_no_action() -> None:
    report = DecisionEngine().decide(_report(), network_snapshot=_snapshot())
    assert report.status is DecisionStatus.NO_ACTION_REQUIRED
    assert report.selected_decisions == []
    assert report.candidate_actions[-1].action_type is DecisionActionType.NO_ACTION


def test_unmatched_warning_is_not_selected() -> None:
    warning = _warning()
    warning.source_id = "unknown:user-01"
    report = DecisionEngine().decide(_report(warning), network_snapshot=_snapshot())
    assert report.status is DecisionStatus.ACTION_UNAVAILABLE
    assert report.selected_decisions == []
    assert report.candidate_actions[0].feasible is False


def test_low_confidence_warning_is_ignored() -> None:
    warning = _warning()
    warning.confidence_score = 0.1
    report = DecisionEngine().decide(_report(warning), network_snapshot=_snapshot())
    assert report.status is DecisionStatus.ACTION_UNAVAILABLE
    assert report.candidate_actions == []


def test_capacity_warning_can_reserve_spectrum() -> None:
    scheduling = SpectrumSchedulingSnapshot(
        timestamp_s=10.0,
        allocations=[],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a",
                total_resource_blocks=20,
                used_resource_blocks=5,
                free_resource_blocks=15,
                utilization_ratio=0.25,
                scheduled_capacity_bps=25_000_000.0,
                remaining_capacity_bps=75_000_000.0,
            )
        ],
    )
    report = DecisionEngine().decide(
        _report(_warning(TelemetryMetric.CAPACITY_BPS)),
        network_snapshot=_snapshot(),
        scheduling_snapshot=scheduling,
    )
    assert report.selected_decisions[0].action.action_type is DecisionActionType.RESERVE_SPECTRUM


def test_timestamp_alignment_is_required() -> None:
    with pytest.raises(ValueError, match="matching timestamps"):
        DecisionEngine().decide(
            _report(_warning(), timestamp_s=11.0),
            network_snapshot=_snapshot(timestamp_s=10.0),
        )


def test_scheduling_timestamp_alignment_is_required() -> None:
    scheduling = SpectrumSchedulingSnapshot(timestamp_s=11.0, allocations=[], utilization=[])
    with pytest.raises(ValueError, match="matching timestamps"):
        DecisionEngine().decide(
            _report(_warning()),
            network_snapshot=_snapshot(),
            scheduling_snapshot=scheduling,
        )


def test_selected_decisions_are_bounded_per_source() -> None:
    warnings = [
        _warning(TelemetryMetric.SINR_DB),
        _warning(TelemetryMetric.LINK_MARGIN_DB),
        _warning(TelemetryMetric.RECEIVED_POWER_DBM),
    ]
    report = DecisionEngine(DecisionConfig(maximum_actions=1)).decide(
        _report(*warnings), network_snapshot=_snapshot()
    )
    assert len(report.selected_decisions) == 1


def test_decision_id_is_deterministic() -> None:
    engine = DecisionEngine()
    first = engine.decide(_report(_warning()), network_snapshot=_snapshot())
    second = engine.decide(_report(_warning()), network_snapshot=_snapshot())
    assert first.selected_decisions[0].decision_id == second.selected_decisions[0].decision_id


def test_no_feasible_alternative_reports_unavailable() -> None:
    network = _snapshot()
    network.associations[0].candidates = [
        _candidate("uav-a", domain=NetworkDomain.AIR, margin=1.5, capacity=50_000_000.0),
        _candidate("gnd-a", domain=NetworkDomain.GROUND, margin=0.2, capacity=100_000_000.0),
    ]
    report = DecisionEngine().decide(_report(_warning()), network_snapshot=network)
    assert report.status is DecisionStatus.ACTION_UNAVAILABLE
    assert all(not item.feasible for item in report.candidate_actions)


def test_config_validation() -> None:
    with pytest.raises(ValidationError):
        DecisionConfig(minimum_confidence=1.5)
