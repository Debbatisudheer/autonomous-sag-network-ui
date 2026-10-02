from __future__ import annotations

from sag_network.domain.traffic import TrafficAllocation, TrafficDemand
from sag_network.domain.unified import UnifiedCandidate
from sag_network.traffic.allocator import allocate_traffic


def evaluate_access_traffic(
    *,
    demands: list[TrafficDemand],
    candidates_by_user: dict[str, list[UnifiedCandidate]],
) -> list[TrafficAllocation]:
    """Evaluate access-resource traffic in deterministic priority order."""
    ordered = sorted(demands, key=lambda demand: (-demand.qos.priority, demand.flow_id))
    allocations: dict[str, float] = {}
    results: list[TrafficAllocation] = []
    for demand in ordered:
        results.append(
            allocate_traffic(
                demand=demand,
                candidates=candidates_by_user.get(demand.user_id, []),
                already_allocated_bps=allocations,
            )
        )
    return sorted(results, key=lambda result: result.flow_id)
