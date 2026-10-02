from __future__ import annotations

from sag_network.domain.ground import GroundCandidate, GroundCell
from sag_network.domain.link import LinkBudget
from sag_network.domain.mobility import MobileUser
from sag_network.physics.link_budget import link_budget
from sag_network.space.geodesy import geodetic_to_ecef, subtract, vector_norm_m


def ground_user_link_state(*, cell: GroundCell, user: MobileUser, timestamp_s: float) -> GroundCandidate:
    """Calculate a terrestrial user-to-cell radio state from WGS84 geometry and link budget."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")
    position = user.position_at(timestamp_s)
    cell_ecef = geodetic_to_ecef(cell.position)
    user_ecef = geodetic_to_ecef(position)
    distance_m = vector_norm_m(subtract(cell_ecef, user_ecef))
    budget: LinkBudget = link_budget(
        distance_m=max(distance_m, 1.0),
        frequency_hz=cell.carrier_frequency_hz,
        bandwidth_hz=cell.bandwidth_hz,
        tx_power_dbm=cell.tx_power_dbm,
        tx_gain_dbi=cell.tx_gain_dbi,
        rx_gain_dbi=cell.rx_gain_dbi,
        noise_figure_db=cell.noise_figure_db,
        propagation_losses=cell.propagation_losses,
        required_sinr_db=cell.required_sinr_db,
    )
    within_range = distance_m <= cell.maximum_service_distance_m
    available = cell.active and user.active and within_range and budget.available
    estimated_capacity_bps = budget.shannon_capacity_bps * cell.scheduler_efficiency
    return GroundCandidate(
        cell_id=cell.cell_id,
        available=available,
        distance_m=distance_m,
        rx_power_dbm=budget.rx_power_dbm,
        noise_power_dbm=budget.noise_power_dbm,
        sinr_db=budget.sinr_db,
        link_margin_db=budget.link_margin_db,
        shannon_capacity_bps=budget.shannon_capacity_bps,
        estimated_capacity_bps=estimated_capacity_bps,
    )
