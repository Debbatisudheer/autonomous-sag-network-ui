from __future__ import annotations

from sag_network.domain.constellation import Constellation
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.space import SatelliteState
from sag_network.space.link import satellite_link_state
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.selection import SatelliteCandidate


def user_satellite_candidates(
    *,
    constellation: Constellation,
    user: MobileUser,
    timestamp_s: float,
    carrier_frequency_hz: float,
    bandwidth_hz: float,
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    noise_figure_db: float,
    propagation_losses: PropagationLosses,
    required_sinr_db: float,
    interference_power_dbm: float | None = None,
) -> list[SatelliteCandidate]:
    """Calculate physically derived satellite candidates for one mobile user."""
    if not user.active:
        return []

    position = user.position_at(timestamp_s)
    candidates: list[SatelliteCandidate] = []
    for satellite in constellation.satellites:
        if not satellite.active:
            continue
        state: SatelliteState = propagate_satellite_state(satellite.orbital_elements, timestamp_s)
        link = satellite_link_state(
            timestamp_s=timestamp_s,
            ground_station_id=user.user_id,
            ground_position=position,
            satellite_position_ecef=state.position_ecef,
            satellite_velocity_ecef=state.velocity_ecef,
            carrier_frequency_hz=carrier_frequency_hz,
            bandwidth_hz=bandwidth_hz,
            tx_power_dbm=tx_power_dbm,
            tx_gain_dbi=tx_gain_dbi,
            rx_gain_dbi=rx_gain_dbi,
            noise_figure_db=noise_figure_db,
            propagation_losses=propagation_losses,
            interference_power_dbm=interference_power_dbm,
            required_sinr_db=required_sinr_db,
            minimum_elevation_deg=satellite.minimum_elevation_deg,
        )
        candidates.append(
            SatelliteCandidate(
                satellite_id=satellite.satellite_id,
                available=bool(link["available"]),
                link_margin_db=float(link["link_margin_db"]),
                elevation_deg=float(link["elevation_deg"]),
                shannon_capacity_bps=float(link["shannon_capacity_bps"]),
                propagation_delay_ms=float(link["propagation_delay_ms"]),
                doppler_shift_hz=float(link["doppler_shift_hz"]),
                predicted_loss_time_s=None,
            )
        )
    return candidates
