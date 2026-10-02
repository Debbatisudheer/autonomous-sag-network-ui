from __future__ import annotations

from sag_network.domain.traffic import QoSMeasurement, TrafficAllocation, TrafficDemand
from sag_network.routing.engine import RouteResult
from sag_network.traffic.qos import qos_is_satisfied


def evaluate_end_to_end_traffic(
    *,
    demands: list[TrafficDemand],
    routes_by_user: dict[str, RouteResult | None],
    link_capacities_bps: dict[str, float],
) -> list[TrafficAllocation]:
    """Perform deterministic end-to-end admission with shared path capacity accounting."""
    residual = dict(link_capacities_bps)
    ordered = sorted(demands, key=lambda demand: (-demand.qos.priority, demand.flow_id))
    results: list[TrafficAllocation] = []

    for demand in ordered:
        route = routes_by_user.get(demand.user_id)
        if route is None:
            results.append(
                TrafficAllocation(
                    flow_id=demand.flow_id,
                    user_id=demand.user_id,
                    admitted=False,
                    requested_bps=demand.demand_bps,
                    allocated_bps=0.0,
                    service_class=demand.qos.service_class,
                    priority=demand.qos.priority,
                    reason="no_end_to_end_route",
                )
            )
            continue

        missing_links = [link_id for link_id in route.link_ids if link_id not in residual]
        if missing_links:
            raise ValueError(
                "route references links without configured capacities: "
                + ", ".join(missing_links)
            )

        path_capacity = min((residual[link_id] for link_id in route.link_ids), default=0.0)
        measurement = QoSMeasurement(
            capacity_bps=path_capacity,
            latency_ms=route.total_latency_ms,
            loss_rate=route.end_to_end_loss_rate,
        )
        if not qos_is_satisfied(demand=demand, measurement=measurement):
            results.append(
                TrafficAllocation(
                    flow_id=demand.flow_id,
                    user_id=demand.user_id,
                    admitted=False,
                    requested_bps=demand.demand_bps,
                    allocated_bps=0.0,
                    service_class=demand.qos.service_class,
                    priority=demand.qos.priority,
                    resource_path=route.node_ids,
                    latency_ms=route.total_latency_ms,
                    loss_rate=route.end_to_end_loss_rate,
                    reason="qos_requirements_not_satisfied",
                )
            )
            continue

        allocated = min(demand.demand_bps, path_capacity)
        for link_id in route.link_ids:
            residual[link_id] -= allocated
        results.append(
            TrafficAllocation(
                flow_id=demand.flow_id,
                user_id=demand.user_id,
                admitted=True,
                requested_bps=demand.demand_bps,
                allocated_bps=allocated,
                service_class=demand.qos.service_class,
                priority=demand.qos.priority,
                resource_path=route.node_ids,
                latency_ms=route.total_latency_ms,
                loss_rate=route.end_to_end_loss_rate,
                reason="qos_requirements_satisfied",
            )
        )

    return sorted(results, key=lambda result: result.flow_id)
