from __future__ import annotations

import math

from sag_network.domain.resource import (
    ResourceUtilization,
    SpectrumAllocation,
    SpectrumAllocationRequest,
    SpectrumResource,
    SpectrumSchedulingSnapshot,
)
from sag_network.domain.traffic import TrafficDemand
from sag_network.domain.unified import UnifiedCandidate


def _request_from_demand(demand: TrafficDemand) -> SpectrumAllocationRequest:
    return SpectrumAllocationRequest(
        flow_id=demand.flow_id,
        user_id=demand.user_id,
        requested_bps=demand.demand_bps,
        minimum_throughput_bps=demand.qos.minimum_throughput_bps,
        priority=demand.qos.priority,
    )


def _required_bps(request: SpectrumAllocationRequest) -> float:
    return max(request.requested_bps, request.minimum_throughput_bps)


def _full_scheduled_capacity_bps(
    *,
    candidate: UnifiedCandidate,
    resource: SpectrumResource,
) -> float:
    return max(candidate.shannon_capacity_bps * resource.scheduler_efficiency, 0.0)


def _resource_selection_key(
    *,
    candidate: UnifiedCandidate,
    resource: SpectrumResource,
    required_bps: float,
) -> tuple[int, float, float, float, str]:
    full_capacity = _full_scheduled_capacity_bps(candidate=candidate, resource=resource)
    if full_capacity <= 0:
        blocks_required = math.inf
    else:
        per_block = full_capacity / resource.total_resource_blocks
        blocks_required = math.ceil(required_bps / per_block)
    return (
        int(candidate.available and blocks_required <= resource.total_resource_blocks),
        -float(blocks_required),
        -candidate.propagation_delay_ms,
        candidate.sinr_db,
        candidate.resource_id,
    )


def schedule_spectrum(
    *,
    timestamp_s: float,
    demands: list[TrafficDemand],
    candidates_by_user: dict[str, list[UnifiedCandidate]],
    resources: dict[str, SpectrumResource],
    used_resource_blocks: dict[str, int] | None = None,
) -> SpectrumSchedulingSnapshot:
    """Allocate shared spectrum as discrete resource blocks in deterministic priority order.

    Capacity is derived from the existing candidate Shannon capacity and a configurable
    scheduler efficiency. No radio measurement is fabricated or recomputed here.
    """
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")

    used = dict(used_resource_blocks or {})
    for resource_id, count in used.items():
        if resource_id not in resources:
            raise ValueError(f"unknown spectrum resource: {resource_id}")
        if count < 0 or count > resources[resource_id].total_resource_blocks:
            raise ValueError(f"invalid used resource blocks for {resource_id}")

    allocations: list[SpectrumAllocation] = []
    ordered_demands = sorted(
        (_request_from_demand(demand) for demand in demands),
        key=lambda request: (-request.priority, request.flow_id),
    )

    for request in ordered_demands:
        required_bps = _required_bps(request)
        candidates = [
            candidate
            for candidate in candidates_by_user.get(request.user_id, [])
            if candidate.available and candidate.resource_id in resources
        ]
        candidates = sorted(
            candidates,
            key=lambda candidate: _resource_selection_key(
                candidate=candidate,
                resource=resources[candidate.resource_id],
                required_bps=required_bps,
            ),
            reverse=True,
        )

        allocation: SpectrumAllocation | None = None
        for candidate in candidates:
            resource = resources[candidate.resource_id]
            capacity = _full_scheduled_capacity_bps(candidate=candidate, resource=resource)
            if capacity <= 0:
                continue
            blocks_required = math.ceil(
                required_bps / (capacity / resource.total_resource_blocks)
            )
            free_blocks = resource.total_resource_blocks - used.get(candidate.resource_id, 0)
            if blocks_required > free_blocks:
                continue
            allocated_bps = min(
                required_bps,
                blocks_required * capacity / resource.total_resource_blocks,
            )
            used[candidate.resource_id] = used.get(candidate.resource_id, 0) + blocks_required
            allocation = SpectrumAllocation(
                flow_id=request.flow_id,
                user_id=request.user_id,
                admitted=True,
                resource_id=candidate.resource_id,
                requested_bps=request.requested_bps,
                required_bps=required_bps,
                allocated_bps=allocated_bps,
                resource_blocks=blocks_required,
                allocated_bandwidth_hz=blocks_required * resource.resource_block_bandwidth_hz,
                reason="spectrum_requirements_satisfied",
            )
            break

        if allocation is None:
            reason = (
                "no_available_spectrum"
                if not candidates
                else "spectrum_requirements_not_satisfied"
            )
            allocation = SpectrumAllocation(
                flow_id=request.flow_id,
                user_id=request.user_id,
                admitted=False,
                requested_bps=request.requested_bps,
                required_bps=required_bps,
                allocated_bps=0.0,
                resource_blocks=0,
                allocated_bandwidth_hz=0.0,
                reason=reason,
            )
        allocations.append(allocation)

    utilization: list[ResourceUtilization] = []
    for resource_id, resource in sorted(resources.items()):
        used_blocks = used.get(resource_id, 0)
        free_blocks = resource.total_resource_blocks - used_blocks
        scheduled_capacity = 0.0
        for candidate_list in candidates_by_user.values():
            matched_candidate = next(
                (item for item in candidate_list if item.resource_id == resource_id),
                None,
            )
            if matched_candidate is not None:
                scheduled_capacity = _full_scheduled_capacity_bps(
                    candidate=matched_candidate,
                    resource=resource,
                )
                break
        per_block_capacity = scheduled_capacity / resource.total_resource_blocks
        utilization.append(
            ResourceUtilization(
                resource_id=resource_id,
                total_resource_blocks=resource.total_resource_blocks,
                used_resource_blocks=used_blocks,
                free_resource_blocks=free_blocks,
                utilization_ratio=used_blocks / resource.total_resource_blocks,
                scheduled_capacity_bps=used_blocks * per_block_capacity,
                remaining_capacity_bps=free_blocks * per_block_capacity,
            )
        )

    return SpectrumSchedulingSnapshot(
        timestamp_s=timestamp_s,
        allocations=sorted(allocations, key=lambda item: item.flow_id),
        utilization=utilization,
    )
