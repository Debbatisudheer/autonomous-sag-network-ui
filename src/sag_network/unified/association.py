from __future__ import annotations

from sag_network.air.link import air_user_link_state
from sag_network.domain.air import AirNetwork
from sag_network.domain.ground import GroundNetwork
from sag_network.domain.mobility import MobileUser
from sag_network.domain.space import SatelliteState
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetwork,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.ground.link import ground_user_link_state
from sag_network.space.link import satellite_link_state
from sag_network.space.orbit import propagate_satellite_state

_SPEED_OF_LIGHT_MPS = 299_792_458.0


def _propagation_delay_ms(distance_m: float) -> float:
    return distance_m / _SPEED_OF_LIGHT_MPS * 1_000.0


def _ground_candidates(
    network: GroundNetwork,
    user: MobileUser,
    timestamp_s: float,
) -> list[UnifiedCandidate]:
    candidates: list[UnifiedCandidate] = []
    for cell in network.cells:
        link = ground_user_link_state(cell=cell, user=user, timestamp_s=timestamp_s)
        candidates.append(
            UnifiedCandidate(
                resource_id=link.cell_id,
                domain=NetworkDomain.GROUND,
                resource_type="ground_cell",
                available=link.available,
                distance_m=link.distance_m,
                rx_power_dbm=link.rx_power_dbm,
                noise_power_dbm=link.noise_power_dbm,
                sinr_db=link.sinr_db,
                link_margin_db=link.link_margin_db,
                shannon_capacity_bps=link.shannon_capacity_bps,
                estimated_capacity_bps=link.estimated_capacity_bps,
                propagation_delay_ms=_propagation_delay_ms(link.distance_m),
            )
        )
    return candidates


def _air_candidates(
    network: AirNetwork,
    user: MobileUser,
    timestamp_s: float,
) -> list[UnifiedCandidate]:
    candidates: list[UnifiedCandidate] = []
    for platform in network.platforms:
        link = air_user_link_state(platform=platform, user=user, timestamp_s=timestamp_s)
        candidates.append(
            UnifiedCandidate(
                resource_id=link.platform_id,
                domain=NetworkDomain.AIR,
                resource_type=link.platform_type.value,
                available=link.available,
                distance_m=link.distance_m,
                rx_power_dbm=link.rx_power_dbm,
                noise_power_dbm=link.noise_power_dbm,
                sinr_db=link.sinr_db,
                link_margin_db=link.link_margin_db,
                shannon_capacity_bps=link.shannon_capacity_bps,
                estimated_capacity_bps=link.estimated_capacity_bps,
                propagation_delay_ms=_propagation_delay_ms(link.distance_m),
                remaining_energy_wh=link.remaining_energy_wh,
                time_to_reserve_s=link.time_to_reserve_s,
            )
        )
    return candidates


def _space_candidates(
    network: UnifiedNetwork,
    user: MobileUser,
    timestamp_s: float,
) -> list[UnifiedCandidate]:
    radio = network.satellite_radio
    position = user.position_at(timestamp_s)
    candidates: list[UnifiedCandidate] = []
    for satellite in network.space.satellites:
        if not satellite.active:
            continue
        state: SatelliteState = propagate_satellite_state(
            satellite.orbital_elements, timestamp_s
        )
        link = satellite_link_state(
            timestamp_s=timestamp_s,
            ground_station_id=user.user_id,
            ground_position=position,
            satellite_position_ecef=state.position_ecef,
            satellite_velocity_ecef=state.velocity_ecef,
            carrier_frequency_hz=radio.carrier_frequency_hz,
            bandwidth_hz=radio.bandwidth_hz,
            tx_power_dbm=radio.tx_power_dbm,
            tx_gain_dbi=radio.tx_gain_dbi,
            rx_gain_dbi=radio.rx_gain_dbi,
            noise_figure_db=radio.noise_figure_db,
            propagation_losses=radio.propagation_losses,
            required_sinr_db=radio.required_sinr_db,
            minimum_elevation_deg=satellite.minimum_elevation_deg,
        )
        candidates.append(
            UnifiedCandidate(
                resource_id=satellite.satellite_id,
                domain=NetworkDomain.SPACE,
                resource_type="leo_satellite",
                available=bool(link["available"]),
                distance_m=float(link["slant_range_m"]),
                rx_power_dbm=float(link["rx_power_dbm"]),
                noise_power_dbm=float(link["noise_power_dbm"]),
                sinr_db=float(link["sinr_db"]),
                link_margin_db=float(link["link_margin_db"]),
                shannon_capacity_bps=float(link["shannon_capacity_bps"]),
                estimated_capacity_bps=float(link["shannon_capacity_bps"]),
                propagation_delay_ms=float(link["propagation_delay_ms"]),
                doppler_shift_hz=float(link["doppler_shift_hz"]),
            )
        )
    return candidates


def _choose_candidate(
    candidates: list[UnifiedCandidate],
    assigned_users: dict[str, int],
) -> UnifiedCandidate | None:
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def sort_key(candidate: UnifiedCandidate) -> tuple[float, float, float, float, float, str]:
        user_count = assigned_users.get(candidate.resource_id, 0)
        shared_rate = candidate.estimated_capacity_bps / (user_count + 1)
        reserve_horizon = (
            float("inf")
            if candidate.time_to_reserve_s is None
            else candidate.time_to_reserve_s
        )
        return (
            shared_rate,
            candidate.link_margin_db,
            reserve_horizon,
            -candidate.propagation_delay_ms,
            candidate.sinr_db,
            candidate.resource_id,
        )

    return max(available, key=sort_key)


def evaluate_unified_network(
    *,
    network: UnifiedNetwork,
    users: list[MobileUser],
    demands_bps: dict[str, float],
    timestamp_s: float,
) -> UnifiedNetworkSnapshot:
    """Compose Ground, Air, and Space candidates into one deterministic baseline state."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")

    assigned_users: dict[str, int] = {}
    associations: list[UnifiedUserAssociation] = []

    for user in sorted(users, key=lambda item: item.user_id):
        demand = demands_bps.get(user.user_id, 0.0)
        if demand < 0:
            raise ValueError(f"demand_bps for {user.user_id} must be non-negative")

        candidates = [
            *_ground_candidates(network.ground, user, timestamp_s),
            *_air_candidates(network.air, user, timestamp_s),
            *_space_candidates(network, user, timestamp_s),
        ]
        selected = _choose_candidate(candidates, assigned_users)
        if selected is None:
            selected_id = None
            selected_domain = None
            allocated = 0.0
        else:
            selected_id = selected.resource_id
            selected_domain = selected.domain
            current_users = assigned_users.get(selected.resource_id, 0) + 1
            allocated = min(demand, selected.estimated_capacity_bps / current_users)
            assigned_users[selected.resource_id] = current_users

        associations.append(
            UnifiedUserAssociation(
                user_id=user.user_id,
                selected_resource_id=selected_id,
                selected_domain=selected_domain,
                demand_bps=demand,
                allocated_capacity_bps=allocated,
                candidates=candidates,
            )
        )

    return UnifiedNetworkSnapshot(timestamp_s=timestamp_s, associations=associations)
