from __future__ import annotations

import pytest

from sag_network.domain.resource import SpectrumResource
from sag_network.domain.traffic import QoSProfile, ServiceClass, TrafficDemand
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate
from sag_network.resource.scheduler import schedule_spectrum


def demand(
    flow_id: str,
    user_id: str = "user-01",
    demand_bps: float = 20e6,
    priority: int = 50,
    minimum_throughput_bps: float = 0.0,
) -> TrafficDemand:
    return TrafficDemand(
        flow_id=flow_id,
        user_id=user_id,
        demand_bps=demand_bps,
        qos=QoSProfile(
            service_class=ServiceClass.INTERACTIVE,
            minimum_throughput_bps=minimum_throughput_bps,
            maximum_latency_ms=100.0,
            maximum_loss_rate=0.02,
            priority=priority,
        ),
    )


def candidate(resource_id: str, *, shannon_capacity_bps: float = 100e6) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.GROUND,
        resource_type="ground_cell",
        available=True,
        distance_m=1_000.0,
        rx_power_dbm=-50.0,
        noise_power_dbm=-95.0,
        sinr_db=30.0,
        link_margin_db=20.0,
        shannon_capacity_bps=shannon_capacity_bps,
        estimated_capacity_bps=75e6,
        propagation_delay_ms=2.0,
    )


def resource(resource_id: str = "gnd-a", bandwidth_hz: float = 20e6) -> SpectrumResource:
    return SpectrumResource(
        resource_id=resource_id,
        bandwidth_hz=bandwidth_hz,
        resource_block_bandwidth_hz=1e6,
        scheduler_efficiency=0.75,
    )


def test_resource_blocks_are_derived_from_bandwidth() -> None:
    assert resource().total_resource_blocks == 20


def test_resource_block_bandwidth_cannot_exceed_total_bandwidth() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        SpectrumResource(
            resource_id="gnd-a",
            bandwidth_hz=10e6,
            resource_block_bandwidth_hz=20e6,
            scheduler_efficiency=0.75,
        )


def test_spectrum_allocation_uses_existing_candidate_capacity() -> None:
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand("flow-1", demand_bps=30e6)],
        candidates_by_user={"user-01": [candidate("gnd-a")]},
        resources={"gnd-a": resource()},
    )
    allocation = snapshot.allocations[0]
    assert allocation.admitted
    assert allocation.resource_blocks == 8
    assert allocation.allocated_bps == pytest.approx(30e6)


def test_shared_spectrum_is_consumed_by_priority_order() -> None:
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[
            demand("flow-low", demand_bps=30e6, priority=10),
            demand("flow-high", demand_bps=30e6, priority=90),
        ],
        candidates_by_user={
            "user-01": [candidate("gnd-a")],
        },
        resources={"gnd-a": resource()},
    )
    allocations = {item.flow_id: item for item in snapshot.allocations}
    assert allocations["flow-high"].admitted
    assert allocations["flow-low"].admitted
    assert snapshot.utilization[0].used_resource_blocks == 16


def test_late_flow_is_rejected_when_no_blocks_remain() -> None:
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[
            demand("flow-high", demand_bps=75e6, priority=90),
            demand("flow-low", demand_bps=5e6, priority=10),
        ],
        candidates_by_user={"user-01": [candidate("gnd-a")]},
        resources={"gnd-a": resource()},
    )
    allocations = {item.flow_id: item for item in snapshot.allocations}
    assert allocations["flow-high"].admitted
    assert not allocations["flow-low"].admitted
    assert allocations["flow-low"].reason == "spectrum_requirements_not_satisfied"


def test_minimum_throughput_is_part_of_spectrum_requirement() -> None:
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand("flow-1", demand_bps=5e6, minimum_throughput_bps=20e6)],
        candidates_by_user={"user-01": [candidate("gnd-a")]},
        resources={"gnd-a": resource()},
    )
    allocation = snapshot.allocations[0]
    assert allocation.admitted
    assert allocation.required_bps == pytest.approx(20e6)
    assert allocation.allocated_bps == pytest.approx(20e6)


def test_unavailable_candidates_are_not_allocated() -> None:
    unavailable = candidate("gnd-a").model_copy(update={"available": False})
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand("flow-1")],
        candidates_by_user={"user-01": [unavailable]},
        resources={"gnd-a": resource()},
    )
    allocation = snapshot.allocations[0]
    assert not allocation.admitted
    assert allocation.reason == "no_available_spectrum"


def test_unknown_used_resource_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown spectrum resource"):
        schedule_spectrum(
            timestamp_s=0.0,
            demands=[demand("flow-1")],
            candidates_by_user={"user-01": [candidate("gnd-a")]},
            resources={"gnd-a": resource()},
            used_resource_blocks={"missing": 1},
        )


def test_resource_utilization_reconciles() -> None:
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand("flow-1", demand_bps=10e6)],
        candidates_by_user={"user-01": [candidate("gnd-a")]},
        resources={"gnd-a": resource()},
    )
    utilization = snapshot.utilization[0]
    assert utilization.used_resource_blocks + utilization.free_resource_blocks == 20
    assert utilization.utilization_ratio == pytest.approx(0.15)


def test_two_resources_choose_the_feasible_spectrum_pool() -> None:
    snapshot = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand("flow-1", demand_bps=60e6)],
        candidates_by_user={
            "user-01": [
                candidate("gnd-a", shannon_capacity_bps=40e6),
                candidate("gnd-b", shannon_capacity_bps=120e6),
            ],
        },
        resources={"gnd-a": resource("gnd-a"), "gnd-b": resource("gnd-b")},
    )
    allocation = snapshot.allocations[0]
    assert allocation.admitted
    assert allocation.resource_id == "gnd-b"


def test_timestamp_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="timestamp_s"):
        schedule_spectrum(
            timestamp_s=-1.0,
            demands=[demand("flow-1")],
            candidates_by_user={"user-01": [candidate("gnd-a")]},
            resources={"gnd-a": resource()},
        )
