from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.domain.resource import ResourceUtilization, SpectrumSchedulingSnapshot
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.optimization.models import (
    ControlAction,
    ControlActionStatus,
    ControlActionType,
    ControlExecutionReport,
    ControlExecutionResult,
    ControlState,
    OptimizationObjective,
    OptimizationPlan,
)
from sag_network.recovery.detector import FailureDetector
from sag_network.recovery.diagnosis import FailureDiagnoser
from sag_network.recovery.engine import FailureRecoveryEngine
from sag_network.recovery.executor import SelfHealingExecutor
from sag_network.recovery.models import (
    FailureRecoveryReport,
    FailureStatus,
    FailureType,
    RecoveryActionType,
    RecoveryConfig,
    RecoveryPlan,
    RootCause,
    SelfHealingState,
)
from sag_network.recovery.planner import RecoveryPlanner
from sag_network.telemetry.models import (
    RealTimeStateSnapshot,
    TelemetryMetric,
    TelemetryQuality,
    TelemetryStateSample,
)


def candidate(
    resource_id: str,
    *,
    available: bool = True,
    margin: float = 10.0,
    capacity: float = 100e6,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.GROUND if resource_id.startswith("gnd") else NetworkDomain.AIR,
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


def snapshot(timestamp_s: float = 10.0, *, two_users: bool = False) -> UnifiedNetworkSnapshot:
    associations = [
        UnifiedUserAssociation(
            user_id="user-01",
            selected_resource_id="uav-a",
            selected_domain=NetworkDomain.AIR,
            demand_bps=20e6,
            allocated_capacity_bps=20e6,
            candidates=[
                candidate("uav-a", available=False, margin=-2.0, capacity=0.0),
                candidate("gnd-a", margin=10.0, capacity=100e6),
            ],
        )
    ]
    if two_users:
        associations.append(
            UnifiedUserAssociation(
                user_id="user-02",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=15e6,
                allocated_capacity_bps=15e6,
                candidates=[
                    candidate("uav-a", available=False, margin=-2.0, capacity=0.0),
                    candidate("gnd-a", margin=9.0, capacity=80e6),
                ],
            )
        )
    return UnifiedNetworkSnapshot(timestamp_s=timestamp_s, associations=associations)


def telemetry_state(
    timestamp_s: float = 10.0,
    *,
    stale: bool = False,
    available: float = 0.0,
    quality: TelemetryQuality = TelemetryQuality.GOOD,
) -> RealTimeStateSnapshot:
    sample_time = timestamp_s - 6.0 if stale else timestamp_s
    return RealTimeStateSnapshot(
        timestamp_s=timestamp_s,
        samples=[
            TelemetryStateSample(
                source_id="uav-a:user-01",
                domain=NetworkDomain.AIR,
                metric=TelemetryMetric.AVAILABLE,
                value=available,
                unit="bool",
                timestamp_s=sample_time,
                sequence=1,
                age_s=timestamp_s - sample_time,
                quality=quality,
                stale=stale,
            )
        ],
    )


def scheduling(timestamp_s: float = 10.0, *, exhausted: bool = False) -> SpectrumSchedulingSnapshot:
    utilization = 0.99 if exhausted else 0.25
    remaining = 0.0 if exhausted else 75e6
    return SpectrumSchedulingSnapshot(
        timestamp_s=timestamp_s,
        allocations=[],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a",
                total_resource_blocks=20,
                used_resource_blocks=20 if exhausted else 5,
                free_resource_blocks=0 if exhausted else 15,
                utilization_ratio=utilization,
                scheduled_capacity_bps=100e6 if exhausted else 25e6,
                remaining_capacity_bps=remaining,
            )
        ],
    )


def test_detector_detects_unavailable_selected_link() -> None:
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(),
        network_snapshot=snapshot(),
    )
    assert any(event.failure_type is FailureType.LINK_FAILURE for event in events)


def test_detector_detects_node_failure_when_all_observed_resource_links_fail() -> None:
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(),
        network_snapshot=snapshot(two_users=True),
    )
    assert any(event.failure_type is FailureType.NODE_FAILURE for event in events)


def test_detector_detects_telemetry_staleness() -> None:
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(stale=True, available=1.0),
        network_snapshot=snapshot(),
    )
    assert any(event.failure_type is FailureType.TELEMETRY_STALE for event in events)


def test_stale_unavailable_telemetry_does_not_create_hard_link_failure() -> None:
    healthy_network = UnifiedNetworkSnapshot(
        timestamp_s=10.0,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=10e6,
                allocated_capacity_bps=10e6,
                candidates=[candidate("uav-a", available=True)],
            )
        ],
    )
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(stale=True, available=0.0),
        network_snapshot=healthy_network,
    )
    assert any(event.failure_type is FailureType.TELEMETRY_STALE for event in events)
    assert not any(event.failure_type is FailureType.LINK_FAILURE for event in events)


def test_detector_detects_resource_exhaustion() -> None:
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(available=1.0),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(exhausted=True),
    )
    assert any(event.failure_type is FailureType.RESOURCE_EXHAUSTION for event in events)


def test_detector_detects_capacity_exhaustion() -> None:
    events = FailureDetector(
        RecoveryConfig(maximum_resource_utilization_ratio=1.0, minimum_remaining_capacity_bps=1.0)
    ).detect(
        telemetry_state=telemetry_state(available=1.0),
        network_snapshot=snapshot(),
        scheduling_snapshot=scheduling(exhausted=True),
    )
    assert any(event.failure_type is FailureType.CAPACITY_EXHAUSTION for event in events)


def test_detector_detects_handover_failure_from_optimization_report() -> None:
    snapshot_ = snapshot()
    action = ControlAction(
        action_id="control-1",
        action_type=ControlActionType.PREPARE_HANDOVER,
        source_id="uav-a:user-01",
        alternative_resource_id="gnd-a",
        timestamp_s=10.0,
        feasible=True,
        priority="critical",
        decision_utility=1.0,
        expected_gain=1.0,
        objective_score=1.0,
        rationale="test",
    )
    optimization = type("OptimizationLike", (), {})()
    optimization.timestamp_s = 10.0
    optimization.plan = OptimizationPlan(
        timestamp_s=10.0,
        objective=OptimizationObjective.BALANCED_UTILITY,
        objective_value=1.0,
        candidate_actions=[action],
        selected_actions=[action],
    )
    optimization.execution = ControlExecutionReport(
        timestamp_s=10.0,
        results=[
            ControlExecutionResult(
                action_id="control-1",
                status=ControlActionStatus.FAILED,
                applied=True,
                verified=False,
                reason="verification failed",
            )
        ],
        resulting_state=ControlState(timestamp_s=10.0),
        all_verified=False,
    )
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(available=1.0),
        network_snapshot=snapshot_,
        optimization_report=optimization,
    )
    assert any(event.failure_type is FailureType.HANDOVER_FAILURE for event in events)


def test_detector_requires_timestamp_alignment() -> None:
    with pytest.raises(ValueError, match="matching timestamps"):
        FailureDetector().detect(
            telemetry_state=telemetry_state(10.0),
            network_snapshot=snapshot(11.0),
        )


def test_diagnoser_maps_link_failure() -> None:
    event = FailureDetector().detect(
        telemetry_state=telemetry_state(),
        network_snapshot=snapshot(),
    )[0]
    diagnosis = FailureDiagnoser().diagnose([event])[0]
    assert diagnosis.root_cause is RootCause.LINK_QUALITY_DEGRADED
    assert RecoveryActionType.REROUTE_FLOW in diagnosis.recommended_action_types


def test_diagnoser_maps_stale_telemetry() -> None:
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(stale=True, available=1.0),
        network_snapshot=snapshot(),
    )
    diagnosis = next(
        item
        for item in FailureDiagnoser().diagnose(events)
        if item.root_cause is RootCause.TELEMETRY_STALE
    )
    assert diagnosis.recommended_action_types == [RecoveryActionType.REFRESH_TELEMETRY]


def test_planner_builds_reroute_action_for_failed_link() -> None:
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(),
        network_snapshot=snapshot(),
    )
    diagnoses = FailureDiagnoser().diagnose(events)
    plan = RecoveryPlanner().plan(events, diagnoses, network_snapshot=snapshot())
    assert any(
        action.action_type is RecoveryActionType.REROUTE_FLOW
        and action.alternative_resource_id == "gnd-a"
        for action in plan.selected_actions
    )


def test_planner_builds_recovery_for_each_user_on_node_failure() -> None:
    network = snapshot(two_users=True)
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(),
        network_snapshot=network,
    )
    node_event = next(event for event in events if event.failure_type is FailureType.NODE_FAILURE)
    diagnosis = FailureDiagnoser().diagnose([node_event])
    plan = RecoveryPlanner().plan([node_event], diagnosis, network_snapshot=network)
    assert len(plan.selected_actions) == 2
    assert {action.source_id for action in plan.selected_actions} == {"user-01", "user-02"}


def test_planner_builds_load_reduction_when_no_alternative_capacity() -> None:
    network = snapshot()
    failed_events = FailureDetector().detect(
        telemetry_state=telemetry_state(available=1.0),
        network_snapshot=network,
        scheduling_snapshot=scheduling(exhausted=True),
    )
    capacity_event = next(
        event for event in failed_events if event.failure_type is FailureType.RESOURCE_EXHAUSTION
    )
    diagnosis = FailureDiagnoser().diagnose([capacity_event])
    plan = RecoveryPlanner().plan(
        [capacity_event],
        diagnosis,
        network_snapshot=network,
        scheduling_snapshot=scheduling(exhausted=True),
    )
    assert plan.selected_actions[0].action_type is RecoveryActionType.REDUCE_LOAD


def test_planner_builds_refresh_for_stale_telemetry() -> None:
    network = snapshot()
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(stale=True, available=1.0),
        network_snapshot=network,
    )
    diagnoses = FailureDiagnoser().diagnose(events)
    plan = RecoveryPlanner().plan(events, diagnoses, network_snapshot=network)
    assert any(
        action.action_type is RecoveryActionType.REFRESH_TELEMETRY
        for action in plan.selected_actions
    )


def test_plan_rejects_selected_action_not_in_candidates() -> None:
    from sag_network.recovery.models import RecoveryAction

    action = RecoveryAction(
        event_id="event-1",
        action_id="recovery-1",
        action_type=RecoveryActionType.REFRESH_TELEMETRY,
        source_id="uav-a:user-01",
        timestamp_s=1.0,
        feasible=True,
        expected_recovery_score=1.0,
        rationale="refresh",
    )
    with pytest.raises(
        ValidationError, match="selected recovery actions must come from candidate actions"
    ):
        RecoveryPlan(timestamp_s=1.0, event_ids=["event-1"], selected_actions=[action])


def test_healing_state_rejects_duplicate_event_ids() -> None:
    with pytest.raises(ValidationError, match="active_event_ids must be unique"):
        SelfHealingState(timestamp_s=1.0, active_event_ids=["a", "a"])


def test_executor_verifies_reroute() -> None:
    network = snapshot()
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(),
        network_snapshot=network,
    )
    diagnoses = FailureDiagnoser().diagnose(events)
    plan = RecoveryPlanner().plan(events, diagnoses, network_snapshot=network)
    result, healing_state, control = SelfHealingExecutor().apply(
        plan,
        network_snapshot=network,
    )
    reroute = next(item for item in result if item.verified)
    assert reroute.status is FailureStatus.RECOVERED
    assert control is not None
    assert control.selected_resources["user-01"] == "gnd-a"
    assert healing_state.version == 1


def test_executor_keeps_stale_failure_active_until_new_sample() -> None:
    network = snapshot()
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(stale=True, available=1.0),
        network_snapshot=network,
    )
    diagnoses = FailureDiagnoser().diagnose(events)
    plan = RecoveryPlanner().plan(events, diagnoses, network_snapshot=network)
    results, healing_state, _ = SelfHealingExecutor().apply(plan, network_snapshot=network)
    stale_action = next(
        result
        for result, action in zip(results, plan.selected_actions, strict=False)
        if action.action_type is RecoveryActionType.REFRESH_TELEMETRY
    )
    assert stale_action.status is FailureStatus.RECOVERING
    assert not stale_action.verified
    assert healing_state.active_event_ids


def test_engine_recovers_failed_link_end_to_end() -> None:
    network = snapshot()
    report = FailureRecoveryEngine().run(
        telemetry_state=telemetry_state(),
        network_snapshot=network,
    )
    assert isinstance(report, FailureRecoveryReport)
    assert report.detected_failures
    assert report.plan.selected_actions
    assert report.execution_results
    assert report.all_recovered
    assert report.resulting_control_state is not None
    assert report.resulting_control_state.selected_resources["user-01"] == "gnd-a"


def test_engine_stale_recovery_is_not_falsely_marked_recovered() -> None:
    network = snapshot()
    report = FailureRecoveryEngine().run(
        telemetry_state=telemetry_state(stale=True, available=1.0),
        network_snapshot=network,
    )
    assert any(
        event.failure_type is FailureType.TELEMETRY_STALE
        for event in report.detected_failures
    )
    assert not report.all_recovered


def test_engine_requires_twin_alignment() -> None:
    from sag_network.digital_twin.engine import DigitalTwin
    from sag_network.digital_twin.models import DigitalTwinConfig

    twin = DigitalTwin(DigitalTwinConfig(twin_id="twin", network_name="demo"))
    twin_snapshot = DigitalTwin.create_snapshot(
        snapshot_id="snap-1",
        timestamp_s=11.0,
        network_name="demo",
        unified_state=snapshot(11.0),
    )
    twin.sync(twin_snapshot)
    with pytest.raises(ValueError, match="matching timestamps"):
        FailureRecoveryEngine().run(
            telemetry_state=telemetry_state(10.0),
            network_snapshot=snapshot(10.0),
            twin_snapshot=twin_snapshot,
        )


def test_failure_event_id_is_stable_across_observation_timestamps() -> None:
    first = FailureDetector().detect(
        telemetry_state=telemetry_state(10.0),
        network_snapshot=snapshot(10.0),
    )
    second = FailureDetector().detect(
        telemetry_state=telemetry_state(11.0),
        network_snapshot=snapshot(11.0),
    )
    first_link = next(event for event in first if event.failure_type is FailureType.LINK_FAILURE)
    second_link = next(event for event in second if event.failure_type is FailureType.LINK_FAILURE)
    assert first_link.event_id == second_link.event_id


def test_recovery_attempt_limit_is_enforced_per_failure_cycle() -> None:
    network = snapshot()
    events = FailureDetector().detect(
        telemetry_state=telemetry_state(stale=True, available=1.0),
        network_snapshot=network,
    )
    stale_event = next(
        event for event in events if event.failure_type is FailureType.TELEMETRY_STALE
    )
    diagnosis = FailureDiagnoser().diagnose([stale_event])
    plan = RecoveryPlanner().plan([stale_event], diagnosis, network_snapshot=network)
    state = SelfHealingState(timestamp_s=10.0)
    executor = SelfHealingExecutor(RecoveryConfig(maximum_recovery_attempts=1))
    _, first_state, _ = executor.apply(plan, network_snapshot=network, state=state)
    second_results, _, _ = executor.apply(plan, network_snapshot=network, state=first_state)
    assert second_results[0].status is FailureStatus.UNRECOVERABLE
    assert "maximum recovery attempts" in second_results[0].reason


def test_control_state_is_carried_and_incremented() -> None:
    network = snapshot()
    state = ControlState(timestamp_s=9.0)
    report = FailureRecoveryEngine().run(
        telemetry_state=telemetry_state(),
        network_snapshot=network,
        control_state=state,
    )
    assert report.resulting_control_state is not None
    assert report.resulting_control_state.version == 1
