from __future__ import annotations

from sag_network.domain.air import AirCandidate, AirPlatform
from sag_network.domain.link import LinkBudget
from sag_network.domain.mobility import MobileUser
from sag_network.physics.link_budget import link_budget
from sag_network.space.geodesy import geodetic_to_ecef, subtract, vector_norm_m


def air_user_link_state(
    *, platform: AirPlatform, user: MobileUser, timestamp_s: float
) -> AirCandidate:
    """Calculate a user-to-aerial-platform radio state from WGS84 geometry and link budget."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")

    platform_position = platform.position_at(timestamp_s)
    user_position = user.position_at(timestamp_s)
    platform_ecef = geodetic_to_ecef(platform_position)
    user_ecef = geodetic_to_ecef(user_position)
    distance_m = vector_norm_m(subtract(platform_ecef, user_ecef))
    budget: LinkBudget = link_budget(
        distance_m=max(distance_m, 1.0),
        frequency_hz=platform.carrier_frequency_hz,
        bandwidth_hz=platform.bandwidth_hz,
        tx_power_dbm=platform.tx_power_dbm,
        tx_gain_dbi=platform.tx_gain_dbi,
        rx_gain_dbi=platform.rx_gain_dbi,
        noise_figure_db=platform.noise_figure_db,
        propagation_losses=platform.propagation_losses,
        required_sinr_db=platform.required_sinr_db,
    )
    within_range = distance_m <= platform.maximum_service_distance_m
    energy_available = platform.energy_available(timestamp_s)
    available = (
        platform.active
        and user.active
        and within_range
        and energy_available
        and budget.available
    )
    estimated_capacity_bps = budget.shannon_capacity_bps * platform.scheduler_efficiency
    return AirCandidate(
        platform_id=platform.platform_id,
        platform_type=platform.platform_type,
        available=available,
        distance_m=distance_m,
        rx_power_dbm=budget.rx_power_dbm,
        noise_power_dbm=budget.noise_power_dbm,
        sinr_db=budget.sinr_db,
        link_margin_db=budget.link_margin_db,
        shannon_capacity_bps=budget.shannon_capacity_bps,
        estimated_capacity_bps=estimated_capacity_bps,
        remaining_energy_wh=platform.energy_remaining_wh(timestamp_s),
        time_to_reserve_s=platform.time_to_reserve_s(timestamp_s),
    )
