from __future__ import annotations

import pytest

from sag_network.domain.traffic import QoSMeasurement, QoSProfile, ServiceClass, TrafficDemand
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate
from sag_network.routing.engine import RouteResult
from sag_network.traffic.allocator import allocate_traffic
from sag_network.traffic.end_to_end import evaluate_end_to_end_traffic
from sag_network.traffic.qos import qos_is_satisfied, qos_profile_is_valid, required_service_rate


def qos(
    *,
    service_class: ServiceClass = ServiceClass.INTERACTIVE,
    minimum_throughput_bps: float = 10e6,
    maximum_latency_ms: float = 100.0,
    maximum_loss_rate: float = 0.02,
    priority: int = 50,
) -> QoSProfile:
    return QoSProfile(
        service_class=service_class,
        minimum_throughput_bps=minimum_throughput_bps,
        maximum_latency_ms=maximum_latency_ms,
        maximum_loss_rate=maximum_loss_rate,
        priority=priority,
    )


def demand(
    flow_id: str,
    user_id: str = "user-01",
    demand_bps: float = 20e6,
    profile: QoSProfile | None = None,
) -> TrafficDemand:
    return TrafficDemand(
        flow_id=flow_id,
        user_id=user_id,
        demand_bps=demand_bps,
        qos=profile or qos(),
    )


def candidate(
    resource_id: str,
    capacity_bps: float = 100e6,
    latency_ms: float = 10.0,
) -> UnifiedCandidate:
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
        shannon_capacity_bps=capacity_bps,
        estimated_capacity_bps=capacity_bps,
        propagation_delay_ms=latency_ms,
    )


def route(
    *,
    capacity_bps: float = 100e6,
    latency_ms: float = 20.0,
    loss_rate: float = 0.01,
) -> RouteResult:
    return RouteResult(
        source_id="user-01",
        destination_id="service",
        node_ids=("user-01", "gnd-a", "core", "service"),
        link_ids=("access", "backhaul", "core"),
        total_latency_ms=latency_ms,
        bottleneck_capacity_bps=capacity_bps,
        end_to_end_loss_rate=loss_rate,
    )


def test_required_service_rate_includes_minimum_throughput() -> None:
    assert required_service_rate(demand("flow-1", demand_bps=5e6)) == pytest.approx(10e6)


def test_qos_satisfied_checks_all_constraints() -> None:
    assert qos_is_satisfied(
        demand=demand("flow-1"),
        measurement=QoSMeasurement(capacity_bps=20e6, latency_ms=20.0, loss_rate=0.01),
    )


def test_access_traffic_is_admitted_when_requirements_fit() -> None:
    result = allocate_traffic(demand=demand("flow-1"), candidates=[candidate("gnd-a")])
    assert result.admitted
    assert result.allocated_bps == pytest.approx(20e6)
    assert result.resource_path == ("gnd-a",)


def test_access_traffic_rejects_insufficient_capacity() -> None:
    result = allocate_traffic(
        demand=demand("flow-1", demand_bps=60e6),
        candidates=[candidate("gnd-a", capacity_bps=50e6)],
    )
    assert not result.admitted
    assert result.reason == "qos_requirements_not_satisfied"


def test_access_traffic_rejects_latency_violation() -> None:
    result = allocate_traffic(
        demand=demand("flow-1", profile=qos(maximum_latency_ms=5.0)),
        candidates=[candidate("gnd-a", latency_ms=10.0)],
    )
    assert not result.admitted


def test_priority_order_gets_shared_access_capacity_first() -> None:
    high = demand("flow-high", demand_bps=60e6, profile=qos(priority=90))
    low = demand("flow-low", demand_bps=60e6, profile=qos(priority=10))
    # The allocator processes in priority order only in service.evaluate_access_traffic.
    from sag_network.traffic.service import evaluate_access_traffic

    results = evaluate_access_traffic(
        demands=[low, high],
        candidates_by_user={"user-01": [candidate("gnd-a", capacity_bps=100e6)]},
    )
    high_result = next(item for item in results if item.flow_id == "flow-high")
    low_result = next(item for item in results if item.flow_id == "flow-low")
    assert high_result.admitted
    assert not low_result.admitted


def test_end_to_end_traffic_uses_route_latency_and_loss() -> None:
    flow = demand("flow-1", profile=qos(maximum_latency_ms=30.0, maximum_loss_rate=0.02))
    result = evaluate_end_to_end_traffic(
        demands=[flow],
        routes_by_user={"user-01": route()},
        link_capacities_bps={"access": 100e6, "backhaul": 50e6, "core": 1e9},
    )[0]
    assert result.admitted
    assert result.latency_ms == pytest.approx(20.0)
    assert result.loss_rate == pytest.approx(0.01)


def test_end_to_end_capacity_is_shared_by_path_links() -> None:
    first = demand("flow-1", demand_bps=40e6, profile=qos(priority=90))
    second = demand("flow-2", demand_bps=40e6, profile=qos(priority=80))
    results = evaluate_end_to_end_traffic(
        demands=[first, second],
        routes_by_user={"user-01": route(), "user-02": RouteResult(
            source_id="user-02",
            destination_id="service",
            node_ids=("user-02", "gnd-a", "core", "service"),
            link_ids=("access", "backhaul", "core"),
            total_latency_ms=20.0,
            bottleneck_capacity_bps=100e6,
            end_to_end_loss_rate=0.01,
        )},
        link_capacities_bps={"access": 100e6, "backhaul": 50e6, "core": 1e9},
    )
    assert next(item for item in results if item.flow_id == "flow-1").admitted
    assert not next(item for item in results if item.flow_id == "flow-2").admitted


def test_no_route_is_rejected() -> None:
    result = evaluate_end_to_end_traffic(
        demands=[demand("flow-1")],
        routes_by_user={"user-01": None},
        link_capacities_bps={},
    )[0]
    assert not result.admitted
    assert result.reason == "no_end_to_end_route"


def test_missing_link_capacity_is_an_error() -> None:
    with pytest.raises(ValueError, match="without configured capacities"):
        evaluate_end_to_end_traffic(
            demands=[demand("flow-1")],
            routes_by_user={"user-01": route()},
            link_capacities_bps={"access": 100e6},
        )


def test_loss_requirement_can_reject_route() -> None:
    flow = demand("flow-1", profile=qos(maximum_loss_rate=0.005))
    result = evaluate_end_to_end_traffic(
        demands=[flow],
        routes_by_user={"user-01": route(loss_rate=0.01)},
        link_capacities_bps={"access": 100e6, "backhaul": 50e6, "core": 1e9},
    )[0]
    assert not result.admitted


def test_qos_profile_validation_is_explicit() -> None:
    assert qos_profile_is_valid(qos())


def test_route_qos_measurement_reuses_end_to_end_metrics() -> None:
    from sag_network.traffic.qos import measure_route_qos

    measurement = measure_route_qos(route(capacity_bps=80e6, latency_ms=22.0, loss_rate=0.015))
    assert measurement is not None
    assert measurement.capacity_bps == pytest.approx(80e6)
    assert measurement.latency_ms == pytest.approx(22.0)
    assert measurement.loss_rate == pytest.approx(0.015)
