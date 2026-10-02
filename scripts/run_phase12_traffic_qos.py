from __future__ import annotations

import json

from sag_network.domain.topology import (
    NetworkTopology,
    TopologyLink,
    TopologyNode,
    TopologyNodeType,
)
from sag_network.domain.traffic import QoSProfile, ServiceClass, TrafficDemand
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate
from sag_network.routing.engine import route_user_to_service
from sag_network.traffic.end_to_end import evaluate_end_to_end_traffic


def node(node_id: str, node_type: TopologyNodeType, domain: str) -> TopologyNode:
    return TopologyNode(node_id=node_id, node_type=node_type, domain=domain)


def link(
    link_id: str,
    source: str,
    target: str,
    capacity_bps: float,
    latency_ms: float,
    loss_rate: float,
) -> TopologyLink:
    return TopologyLink(
        link_id=link_id,
        source_id=source,
        target_id=target,
        capacity_bps=capacity_bps,
        latency_ms=latency_ms,
        loss_rate=loss_rate,
    )


def candidate(resource_id: str, capacity_bps: float, latency_ms: float) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.GROUND,
        resource_type="ground_cell",
        available=True,
        distance_m=1_000.0,
        rx_power_dbm=-50.0,
        noise_power_dbm=-95.0,
        sinr_db=35.0,
        link_margin_db=25.0,
        shannon_capacity_bps=capacity_bps,
        estimated_capacity_bps=capacity_bps,
        propagation_delay_ms=latency_ms,
    )


network = NetworkTopology(
    name="sag-phase12-demo",
    nodes=[
        node("user-01", TopologyNodeType.USER, "unified"),
        node("user-02", TopologyNodeType.USER, "unified"),
        node("gnd-a", TopologyNodeType.GROUND_CELL, "ground"),
        node("gnd-b", TopologyNodeType.GROUND_CELL, "ground"),
        node("ground-gw", TopologyNodeType.GROUND_GATEWAY, "ground"),
        node("core", TopologyNodeType.CORE, "core"),
        node("service", TopologyNodeType.SERVICE, "service"),
    ],
    links=[
        link("gnd-a-gw", "gnd-a", "ground-gw", 60e6, 5.0, 0.002),
        link("gnd-b-gw", "gnd-b", "ground-gw", 30e6, 8.0, 0.002),
        link("ground-core", "ground-gw", "core", 80e6, 8.0, 0.002),
        link("core-service", "core", "service", 1e9, 2.0, 0.001),
    ],
)

candidates_by_user = {
    "user-01": [candidate("gnd-a", 60e6, 1.0), candidate("gnd-b", 30e6, 2.0)],
    "user-02": [candidate("gnd-a", 60e6, 1.0), candidate("gnd-b", 30e6, 2.0)],
}

routes = {
    user_id: route_user_to_service(
        topology=network,
        user_id=user_id,
        service_id="service",
        candidates=candidates,
    )
    for user_id, candidates in candidates_by_user.items()
}

flows = [
    TrafficDemand(
        flow_id="flow-video",
        user_id="user-01",
        demand_bps=40e6,
        qos=QoSProfile(
            service_class=ServiceClass.STREAMING,
            minimum_throughput_bps=25e6,
            maximum_latency_ms=100.0,
            maximum_loss_rate=0.02,
            priority=90,
        ),
    ),
    TrafficDemand(
        flow_id="flow-interactive",
        user_id="user-02",
        demand_bps=40e6,
        qos=QoSProfile(
            service_class=ServiceClass.INTERACTIVE,
            minimum_throughput_bps=10e6,
            maximum_latency_ms=50.0,
            maximum_loss_rate=0.01,
            priority=50,
        ),
    ),
]

# The two flows intentionally share the same Ground path, exercising admission under contention.

result = evaluate_end_to_end_traffic(
    demands=flows,
    routes_by_user=routes,
    link_capacities_bps={
        "access:user-01:gnd-a": 60e6,
        "access:user-01:gnd-b": 30e6,
        "access:user-02:gnd-a": 60e6,
        "access:user-02:gnd-b": 30e6,
        "gnd-a-gw": 60e6,
        "gnd-b-gw": 30e6,
        "ground-core": 80e6,
        "core-service": 1e9,
    },
)

print(json.dumps([item.model_dump(mode="json") for item in result], indent=2))
