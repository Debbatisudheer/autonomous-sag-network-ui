from __future__ import annotations

from collections.abc import Iterable

from sag_network.domain.mobility import MobileUser
from sag_network.domain.unified import UnifiedNetwork
from sag_network.domain.unified_handover import UnifiedHandoverEvent
from sag_network.unified.association import evaluate_unified_network
from sag_network.unified.handover import UnifiedHandoverController


def run_cross_domain_mobility(
    *,
    network: UnifiedNetwork,
    users: list[MobileUser],
    demands_bps: dict[str, float],
    timestamps_s: Iterable[float],
    controllers: dict[str, UnifiedHandoverController] | None = None,
) -> dict[str, list[UnifiedHandoverEvent]]:
    """Run unified snapshots through one stateful cross-domain controller per user."""
    state = controllers if controllers is not None else {}
    events_by_user: dict[str, list[UnifiedHandoverEvent]] = {
        user.user_id: [] for user in users
    }
    previous_timestamp_s: float | None = None

    for timestamp_s in timestamps_s:
        if timestamp_s < 0:
            raise ValueError("timestamps_s must contain non-negative values")
        if previous_timestamp_s is not None and timestamp_s < previous_timestamp_s:
            raise ValueError("timestamps_s must be non-decreasing")
        previous_timestamp_s = timestamp_s
        snapshot = evaluate_unified_network(
            network=network,
            users=users,
            demands_bps=demands_bps,
            timestamp_s=timestamp_s,
        )
        for association in snapshot.associations:
            controller = state.setdefault(association.user_id, UnifiedHandoverController())
            event = controller.update(
                user_id=association.user_id,
                timestamp_s=timestamp_s,
                candidates=association.candidates,
            )
            events_by_user[association.user_id].append(event)

    return events_by_user
