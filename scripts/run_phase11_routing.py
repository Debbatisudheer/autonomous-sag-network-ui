from __future__ import annotations

import json

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


network = NetworkTopology(
    name="sag-phase11-demo",
    nodes=[
        node("user-01", TopologyNodeType.USER, "unified"),
        node("gnd-a", TopologyNodeType.GROUND_CELL, "ground"),
        node("uav-a", TopologyNodeType.UAV, "air"),
        node("leo-a", TopologyNodeType.LEO_SATELLITE, "space"),
        node("ground-gw", TopologyNodeType.GROUND_GATEWAY, "ground"),
        node("air-gw", TopologyNodeType.AIR_GATEWAY, "air"),
        node("space-gw", TopologyNodeType.SPACE_GATEWAY, "space"),
        node("core", TopologyNodeType.CORE, "core"),
        node("service", TopologyNodeType.SERVICE, "service"),
    ],
    links=[
        TopologyLink(link_id="gnd-gw", source_id="gnd-a", target_id="ground-gw", capacity_bps=1e9, latency_ms=5.0, loss_rate=0.001),
        TopologyLink(link_id="uav-gw", source_id="uav-a", target_id="air-gw", capacity_bps=500e6, latency_ms=8.0, loss_rate=0.002),
        TopologyLink(link_id="sat-gw", source_id="leo-a", target_id="space-gw", capacity_bps=250e6, latency_ms=12.0, loss_rate=0.003),
        TopologyLink(link_id="ground-core", source_id="ground-gw", target_id="core", capacity_bps=1e9, latency_ms=8.0, loss_rate=0.001),
        TopologyLink(link_id="air-core", source_id="air-gw", target_id="core", capacity_bps=500e6, latency_ms=10.0, loss_rate=0.002),
        TopologyLink(link_id="space-core", source_id="space-gw", target_id="core", capacity_bps=250e6, latency_ms=20.0, loss_rate=0.003),
        TopologyLink(link_id="core-service", source_id="core", target_id="service", capacity_bps=10e9, latency_ms=2.0, loss_rate=0.0001),
    ],
)


def candidate(
    resource_id: str,
    domain: NetworkDomain,
    resource_type: str,
    capacity_bps: float,
    latency_ms: float,
    available: bool = True,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=domain,
        resource_type=resource_type,
        available=available,
        distance_m=1.0,
        rx_power_dbm=-50.0,
        noise_power_dbm=-95.0,
        sinr_db=45.0,
        link_margin_db=35.0,
        shannon_capacity_bps=capacity_bps,
        estimated_capacity_bps=capacity_bps,
        propagation_delay_ms=latency_ms,
    )


candidates = [
    candidate("gnd-a", NetworkDomain.GROUND, "ground_cell", 100e6, 1.0),
    candidate("uav-a", NetworkDomain.AIR, "uav", 80e6, 3.0),
    candidate("leo-a", NetworkDomain.SPACE, "leo_satellite", 60e6, 5.0),
]

route = route_user_to_service(
    topology=network,
    user_id="user-01",
    service_id="service",
    candidates=candidates,
)

print(json.dumps({"route": None if route is None else {
    "nodes": route.node_ids,
    "links": route.link_ids,
    "total_latency_ms": route.total_latency_ms,
    "bottleneck_capacity_bps": route.bottleneck_capacity_bps,
    "end_to_end_loss_rate": route.end_to_end_loss_rate,
}}, indent=2))
