from __future__ import annotations

from dataclasses import dataclass

from sag_network.domain.traffic import QoSMeasurement, TrafficAllocation, TrafficDemand
from sag_network.domain.unified import UnifiedCandidate
from sag_network.traffic.qos import qos_is_satisfied


@dataclass(frozen=True)
class TrafficCandidate:
    """Candidate access resource with its normalized QoS view."""

    candidate: UnifiedCandidate
    measurement: QoSMeasurement


def _candidate_key(item: TrafficCandidate, demand: TrafficDemand) -> tuple[int, float, float, float, str]:
    qos_met = int(qos_is_satisfied(demand=demand, measurement=item.measurement))
    capacity_margin = item.measurement.capacity_bps - max(
        demand.demand_bps, demand.qos.minimum_throughput_bps
    )
    return (
        qos_met,
        capacity_margin,
        -item.measurement.latency_ms,
        -item.measurement.loss_rate,
        item.candidate.resource_id,
    )


def allocate_traffic(
    *,
    demand: TrafficDemand,
    candidates: list[UnifiedCandidate],
    already_allocated_bps: dict[str, float] | None = None,
) -> TrafficAllocation:
    """Admit traffic using measured candidate capacity and explicit QoS constraints."""
    allocations = already_allocated_bps if already_allocated_bps is not None else {}
    traffic_candidates = [
        TrafficCandidate(
            candidate=candidate,
            measurement=QoSMeasurement(
                capacity_bps=candidate.estimated_capacity_bps,
                latency_ms=candidate.propagation_delay_ms,
                loss_rate=0.0,
            ),
        )
        for candidate in candidates
        if candidate.available
    ]
    if not traffic_candidates:
        return TrafficAllocation(
            flow_id=demand.flow_id,
            user_id=demand.user_id,
            admitted=False,
            requested_bps=demand.demand_bps,
            allocated_bps=0.0,
            service_class=demand.qos.service_class,
            priority=demand.qos.priority,
            reason="no_available_resource",
        )

    ordered = sorted(
        traffic_candidates,
        key=lambda item: _candidate_key(item, demand),
        reverse=True,
    )
    for item in ordered:
        resource_id = item.candidate.resource_id
        residual = max(item.measurement.capacity_bps - allocations.get(resource_id, 0.0), 0.0)
        measurement = item.measurement.model_copy(update={"capacity_bps": residual})
        if not qos_is_satisfied(demand=demand, measurement=measurement):
            continue
        allocated = min(demand.demand_bps, residual)
        allocations[resource_id] = allocations.get(resource_id, 0.0) + allocated
        return TrafficAllocation(
            flow_id=demand.flow_id,
            user_id=demand.user_id,
            admitted=True,
            requested_bps=demand.demand_bps,
            allocated_bps=allocated,
            service_class=demand.qos.service_class,
            priority=demand.qos.priority,
            resource_path=(resource_id,),
            latency_ms=measurement.latency_ms,
            loss_rate=measurement.loss_rate,
            reason="qos_requirements_satisfied",
        )

    return TrafficAllocation(
        flow_id=demand.flow_id,
        user_id=demand.user_id,
        admitted=False,
        requested_bps=demand.demand_bps,
        allocated_bps=0.0,
        service_class=demand.qos.service_class,
        priority=demand.qos.priority,
        reason="qos_requirements_not_satisfied",
    )
