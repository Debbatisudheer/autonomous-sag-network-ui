from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.domain.topology import (
    NetworkTopology,
    TopologyLink,
    TopologyNode,
    TopologyNodeType,
)
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate
from sag_network.routing.engine import route_user_to_service


def node(node_id: str, node_type: TopologyNodeType, domain: str) -> TopologyNode:
    return TopologyNode(node_id=node_id, node_type=node_type, domain=domain)


def link(
    link_id: str,
    source: str,
    target: str,
    capacity_bps: float,
    latency_ms: float,
    loss_rate: float = 0.0,
) -> TopologyLink:
    return TopologyLink(
        link_id=link_id,
        source_id=source,
        target_id=target,
        capacity_bps=capacity_bps,
        latency_ms=latency_ms,
        loss_rate=loss_rate,
    )


def candidate(resource_id: str, latency_ms: float, capacity_bps: float) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.GROUND,
        resource_type="test_resource",
        available=True,
        distance_m=1.0,
        rx_power_dbm=-50.0,
        noise_power_dbm=-95.0,
        sinr_db=45.0,
        link_margin_db=35.0,
        shannon_capacity_bps=capacity_bps,
        estimated_capacity_bps=capacity_bps,
        propagation_delay_ms=latency_ms,
    )


def make_topology() -> NetworkTopology:
    return NetworkTopology(
        name="routing-test",
        nodes=[
            node("user-01", TopologyNodeType.USER, "unified"),
            node("gnd-a", TopologyNodeType.GROUND_CELL, "ground"),
            node("gnd-b", TopologyNodeType.GROUND_CELL, "ground"),
            node("core", TopologyNodeType.CORE, "core"),
            node("internet", TopologyNodeType.SERVICE, "service"),
        ],
        links=[
            link("gnd-a-core", "gnd-a", "core", 100e6, 10.0),
            link("gnd-b-core", "gnd-b", "core", 100e6, 20.0),
            link("core-internet", "core", "internet", 1e9, 5.0),
        ],
    )


def test_route_prefers_lowest_latency_feasible_access() -> None:
    result = route_user_to_service(
        topology=make_topology(),
        user_id="user-01",
        service_id="internet",
        candidates=[candidate("gnd-a", 2.0, 80e6), candidate("gnd-b", 1.0, 80e6)],
    )

    assert result is not None
    assert result.node_ids == ("user-01", "gnd-a", "core", "internet")
    assert result.total_latency_ms == pytest.approx(17.0)
    assert result.bottleneck_capacity_bps == pytest.approx(80e6)
    assert result.end_to_end_loss_rate == pytest.approx(0.0)


def test_unavailable_candidate_is_not_routable() -> None:
    topology = make_topology()
    result = route_user_to_service(
        topology=topology,
        user_id="user-01",
        service_id="internet",
        candidates=[
            UnifiedCandidate(
                **candidate("gnd-a", 2.0, 80e6).model_dump() | {"available": False}
            ),
            candidate("gnd-b", 1.0, 80e6),
        ],
    )
    assert result is not None
    assert result.node_ids[1] == "gnd-b"


def test_inactive_backhaul_blocks_path() -> None:
    topology = make_topology()
    topology.links[0].active = False
    topology.links[1].active = False
    result = route_user_to_service(
        topology=topology,
        user_id="user-01",
        service_id="internet",
        candidates=[candidate("gnd-a", 2.0, 80e6), candidate("gnd-b", 1.0, 80e6)],
    )
    assert result is None


def test_route_capacity_uses_bottleneck() -> None:
    topology = make_topology()
    topology.links[1].capacity_bps = 30e6
    result = route_user_to_service(
        topology=topology,
        user_id="user-01",
        service_id="internet",
        candidates=[candidate("gnd-b", 1.0, 80e6)],
    )
    assert result is not None
    assert result.bottleneck_capacity_bps == pytest.approx(30e6)


def test_end_to_end_loss_combines_independent_link_losses() -> None:
    topology = make_topology()
    topology.links[1].loss_rate = 0.10
    topology.links[2].loss_rate = 0.20
    result = route_user_to_service(
        topology=topology,
        user_id="user-01",
        service_id="internet",
        candidates=[candidate("gnd-b", 1.0, 80e6)],
    )
    assert result is not None
    assert result.end_to_end_loss_rate == pytest.approx(0.28)



def test_inactive_node_blocks_path() -> None:
    topology = make_topology()
    core = next(node for node in topology.nodes if node.node_id == "core")
    core.active = False
    result = route_user_to_service(
        topology=topology,
        user_id="user-01",
        service_id="internet",
        candidates=[candidate("gnd-a", 2.0, 80e6)],
    )
    assert result is None


def test_unknown_candidate_resource_rejected() -> None:
    with pytest.raises(ValueError, match="candidate resources"):
        route_user_to_service(
            topology=make_topology(),
            user_id="user-01",
            service_id="internet",
            candidates=[candidate("missing", 1.0, 80e6)],
        )

def test_unknown_nodes_raise() -> None:
    with pytest.raises(ValueError, match="unknown user node"):
        route_user_to_service(
            topology=make_topology(),
            user_id="missing",
            service_id="internet",
            candidates=[],
        )


def test_duplicate_node_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        NetworkTopology(
            name="invalid",
            nodes=[
                node("n1", TopologyNodeType.USER, "unified"),
                node("n1", TopologyNodeType.SERVICE, "service"),
            ],
            links=[link("l1", "n1", "n1", 1e6, 1.0)],
        )


def test_invalid_link_endpoint_rejected() -> None:
    with pytest.raises(ValidationError):
        NetworkTopology(
            name="invalid",
            nodes=[node("n1", TopologyNodeType.USER, "unified"), node("n2", TopologyNodeType.SERVICE, "service")],
            links=[link("l1", "n1", "missing", 1e6, 1.0)],
        )
