from __future__ import annotations

from sag_network.domain.ground import (
    GroundCandidate,
    GroundNetwork,
    GroundNetworkSnapshot,
    GroundUserAssociation,
)
from sag_network.domain.mobility import MobileUser
from sag_network.ground.link import ground_user_link_state


def _choose_cell(candidates: list[GroundCandidate], assigned_users: dict[str, int]) -> GroundCandidate | None:
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def sort_key(candidate: GroundCandidate) -> tuple[float, float, float, float]:
        user_count = assigned_users.get(candidate.cell_id, 0)
        estimated_shared_rate = candidate.estimated_capacity_bps / (user_count + 1)
        return (
            estimated_shared_rate,
            candidate.link_margin_db,
            candidate.estimated_capacity_bps,
            -candidate.distance_m,
        )

    return max(available, key=sort_key)


def evaluate_ground_network(
    *,
    network: GroundNetwork,
    users: list[MobileUser],
    demands_bps: dict[str, float],
    timestamp_s: float,
) -> GroundNetworkSnapshot:
    """Build a deterministic multi-user terrestrial state using greedy load-aware association.

    The allocated capacity is a scheduling ceiling based on an equal-share baseline. It is
    not a prediction of application throughput and does not model scheduler-specific PHY/MAC
    overhead beyond the configured scheduler_efficiency factor.
    """
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")

    assigned_users: dict[str, int] = {}
    associations: list[GroundUserAssociation] = []
    ordered_users = sorted(users, key=lambda user: user.user_id)

    for user in ordered_users:
        demand = demands_bps.get(user.user_id, 0.0)
        if demand < 0:
            raise ValueError(f"demand_bps for {user.user_id} must be non-negative")
        candidates = [
            ground_user_link_state(cell=cell, user=user, timestamp_s=timestamp_s)
            for cell in network.cells
        ]
        selected = _choose_cell(candidates, assigned_users)
        selected_id = None if selected is None else selected.cell_id
        if selected is None:
            allocated = 0.0
        else:
            current_users = assigned_users.get(selected.cell_id, 0) + 1
            allocated = min(demand, selected.estimated_capacity_bps / current_users)
            assigned_users[selected.cell_id] = current_users
        associations.append(
            GroundUserAssociation(
                user_id=user.user_id,
                selected_cell_id=selected_id,
                demand_bps=demand,
                allocated_capacity_bps=allocated,
                candidates=candidates,
            )
        )

    return GroundNetworkSnapshot(timestamp_s=timestamp_s, associations=associations)
