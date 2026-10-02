from __future__ import annotations

import heapq
from dataclasses import dataclass

from sag_network.domain.topology import NetworkTopology, TopologyLink
from sag_network.domain.unified import UnifiedCandidate


@dataclass(frozen=True)
class UserAccessLink:
    """The modeled radio access path between a user and one network resource."""

    resource_id: str
    capacity_bps: float
    latency_ms: float
    loss_rate: float = 0.0


@dataclass(frozen=True)
class RouteResult:
    """A selected end-to-end route and its limiting engineering metrics."""

    source_id: str
    destination_id: str
    node_ids: tuple[str, ...]
    link_ids: tuple[str, ...]
    total_latency_ms: float
    bottleneck_capacity_bps: float
    end_to_end_loss_rate: float


def _path_objective(path_latency_ms: float, path_capacity_bps: float, node_ids: tuple[str, ...]) -> tuple[float, float, tuple[str, ...]]:
    return (path_latency_ms, -path_capacity_bps, node_ids)


def route_user_to_service(
    *,
    topology: NetworkTopology,
    user_id: str,
    service_id: str,
    candidates: list[UnifiedCandidate],
) -> RouteResult | None:
    """Select the lowest-latency feasible path subject to candidate and link availability."""
    nodes_by_id = {node.node_id: node for node in topology.nodes}
    if user_id not in nodes_by_id:
        raise ValueError(f"unknown user node: {user_id}")
    if service_id not in nodes_by_id:
        raise ValueError(f"unknown service node: {service_id}")

    active_node_ids = {node.node_id for node in topology.nodes if node.active}
    if user_id not in active_node_ids:
        raise ValueError(f"user node is inactive: {user_id}")
    if service_id not in active_node_ids:
        raise ValueError(f"service node is inactive: {service_id}")

    active_links: dict[str, list[TopologyLink]] = {}
    for link in topology.links:
        if link.active and link.source_id in active_node_ids and link.target_id in active_node_ids:
            active_links.setdefault(link.source_id, []).append(link)

    candidate_by_id = {candidate.resource_id: candidate for candidate in candidates if candidate.available}
    unknown_candidate_ids = sorted(set(candidate_by_id) - active_node_ids)
    if unknown_candidate_ids:
        raise ValueError(
            "candidate resources must reference active topology nodes: "
            + ", ".join(unknown_candidate_ids)
        )
    graph_links: dict[str, list[TopologyLink]] = {
        source: list(links) for source, links in active_links.items()
    }

    user_access_links: list[TopologyLink] = []
    for candidate in candidate_by_id.values():
        user_access_links.append(
            TopologyLink(
                link_id=f"access:{user_id}:{candidate.resource_id}",
                source_id=user_id,
                target_id=candidate.resource_id,
                capacity_bps=candidate.estimated_capacity_bps,
                latency_ms=candidate.propagation_delay_ms,
                loss_rate=0.0,
            )
        )
    graph_links[user_id] = user_access_links

    best: tuple[tuple[float, float, tuple[str, ...]], RouteResult] | None = None
    queue: list[tuple[tuple[float, float, tuple[str, ...]], str, float, float, tuple[str, ...], tuple[str, ...], float]] = []
    initial_state: tuple[float, float, tuple[str, ...], tuple[str, ...], float] = (
        0.0, 0.0, (user_id,), (), 0.0
    )
    initial_objective = _path_objective(0.0, float("inf"), (user_id,))
    heapq.heappush(queue, (initial_objective, user_id, *initial_state))
    best_seen: dict[str, tuple[float, float, tuple[str, ...]]] = {}

    while queue:
        _, current, latency_ms, bottleneck_capacity_bps, path_nodes, path_links, loss_probability = heapq.heappop(queue)
        objective = _path_objective(
            latency_ms,
            bottleneck_capacity_bps if bottleneck_capacity_bps > 0 else float("inf"),
            path_nodes,
        )
        prior = best_seen.get(current)
        if prior is not None and objective >= prior:
            continue
        best_seen[current] = objective

        if current == service_id:
            result = RouteResult(
                source_id=user_id,
                destination_id=service_id,
                node_ids=path_nodes,
                link_ids=path_links,
                total_latency_ms=latency_ms,
                bottleneck_capacity_bps=bottleneck_capacity_bps if bottleneck_capacity_bps > 0 else float("inf"),
                end_to_end_loss_rate=loss_probability,
            )
            if best is None or result.total_latency_ms < best[1].total_latency_ms:
                best = (objective, result)
            continue

        for link in graph_links.get(current, []):
            if link.target_id in path_nodes:
                continue
            new_latency = latency_ms + link.latency_ms
            new_capacity = min(bottleneck_capacity_bps, link.capacity_bps) if bottleneck_capacity_bps > 0 else link.capacity_bps
            new_loss = 1.0 - (1.0 - loss_probability) * (1.0 - link.loss_rate)
            new_nodes = (*path_nodes, link.target_id)
            new_links = (*path_links, link.link_id)
            new_objective = _path_objective(new_latency, new_capacity, new_nodes)
            heapq.heappush(
                queue,
                (new_objective, link.target_id, new_latency, new_capacity, new_nodes, new_links, new_loss),
            )

    return None if best is None else best[1]
