from __future__ import annotations

from collections.abc import Callable, Iterable

from sag_network.domain.models import LinkObservation, NetworkNode
from sag_network.physics.link_budget import (
    free_space_path_loss_db,
    received_power_dbm,
    sinr_db,
    thermal_noise_power_dbm,
)

DistanceFn = Callable[[NetworkNode, NetworkNode], float]


def simulate_links(
    *,
    timestamp_s: float,
    source: NetworkNode,
    targets: Iterable[NetworkNode],
    distance_fn: DistanceFn,
    frequency_hz: float,
    bandwidth_hz: float,
    noise_figure_db: float,
) -> list[LinkObservation]:
    """Generate deterministic link observations from the current node state."""
    noise_dbm = thermal_noise_power_dbm(bandwidth_hz, noise_figure_db)
    observations: list[LinkObservation] = []
    for target in targets:
        if not target.active:
            continue
        distance_m = distance_fn(source, target)
        path_loss_db = free_space_path_loss_db(distance_m, frequency_hz)
        rx_power = received_power_dbm(
            source.tx_power_dbm,
            source.tx_gain_dbi,
            target.rx_gain_dbi,
            path_loss_db,
        )
        observations.append(
            LinkObservation(
                timestamp_s=timestamp_s,
                source_id=source.node_id,
                target_id=target.node_id,
                distance_m=distance_m,
                rx_power_dbm=rx_power,
                noise_power_dbm=noise_dbm,
                sinr_db=sinr_db(rx_power, noise_dbm),
                latency_ms=(distance_m / 299_792_458.0) * 2_000,
                available_bps=target.available_capacity_bps,
                visible=True,
            )
        )
    return observations
