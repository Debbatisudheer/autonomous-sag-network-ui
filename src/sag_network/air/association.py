from __future__ import annotations

from sag_network.air.link import air_user_link_state
from sag_network.domain.air import (
    AirCandidate,
    AirNetwork,
    AirNetworkSnapshot,
    AirUserAssociation,
)
from sag_network.domain.mobility import MobileUser


def _choose_platform(
    candidates: list[AirCandidate], assigned_users: dict[str, int]
) -> AirCandidate | None:
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def sort_key(candidate: AirCandidate) -> tuple[float, float, float, float, float]:
        user_count = assigned_users.get(candidate.platform_id, 0)
        estimated_shared_rate = candidate.estimated_capacity_bps / (user_count + 1)
        reserve_time = candidate.time_to_reserve_s
        reserve_horizon = float("inf") if reserve_time is None else reserve_time
        return (
            estimated_shared_rate,
            candidate.link_margin_db,
            reserve_horizon,
            candidate.estimated_capacity_bps,
            -candidate.distance_m,
        )

    return max(available, key=sort_key)


def evaluate_air_network(
    *,
    network: AirNetwork,
    users: list[MobileUser],
    demands_bps: dict[str, float],
    timestamp_s: float,
) -> AirNetworkSnapshot:
    """Build deterministic multi-user aerial state using greedy load/energy-aware association."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")

    assigned_users: dict[str, int] = {}
    associations: list[AirUserAssociation] = []
    ordered_users = sorted(users, key=lambda user: user.user_id)

    for user in ordered_users:
        demand = demands_bps.get(user.user_id, 0.0)
        if demand < 0:
            raise ValueError(f"demand_bps for {user.user_id} must be non-negative")
        candidates = [
            air_user_link_state(platform=platform, user=user, timestamp_s=timestamp_s)
            for platform in network.platforms
        ]
        selected = _choose_platform(candidates, assigned_users)
        selected_id = None if selected is None else selected.platform_id
        if selected is None:
            allocated = 0.0
        else:
            current_users = assigned_users.get(selected.platform_id, 0) + 1
            allocated = min(demand, selected.estimated_capacity_bps / current_users)
            assigned_users[selected.platform_id] = current_users
        associations.append(
            AirUserAssociation(
                user_id=user.user_id,
                selected_platform_id=selected_id,
                demand_bps=demand,
                allocated_capacity_bps=allocated,
                candidates=candidates,
            )
        )

    return AirNetworkSnapshot(timestamp_s=timestamp_s, associations=associations)
