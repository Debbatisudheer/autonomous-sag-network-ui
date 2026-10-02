from __future__ import annotations

from sag_network.channel.evaluator import NTNChannelModel
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.space import CartesianPoint
from sag_network.ephemeris.models import RealSatelliteDefinition
from sag_network.ephemeris.reference import SimulationStateProvider
from sag_network.space.link import satellite_link_state
from sag_network.space.selection import SatelliteCandidate


class RealEphemerisConstellation:
    """Runtime collection of real-ephemeris-backed satellites."""

    def __init__(
        self,
        satellites: list[tuple[RealSatelliteDefinition, SimulationStateProvider]],
    ) -> None:
        if not satellites:
            raise ValueError("at least one real satellite is required")
        ids = [definition.satellite_id for definition, _ in satellites]
        if len(ids) != len(set(ids)):
            raise ValueError("real satellite IDs must be unique")
        self.satellites = tuple(satellites)


def user_real_satellite_candidates(
    *,
    constellation: RealEphemerisConstellation,
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
    simulation_epoch_timestamp_s: float = 0.0,
    channel_model: NTNChannelModel | None = None,
) -> list[SatelliteCandidate]:
    """Build existing-style candidates using real SGP4 satellite states."""
    if not user.active:
        return []
    if timestamp_s < simulation_epoch_timestamp_s:
        raise ValueError("timestamp_s precedes configured simulation epoch")

    position = user.position_at(timestamp_s)
    candidates: list[SatelliteCandidate] = []
    for definition, adapter in constellation.satellites:
        if not definition.active:
            continue
        state = adapter.state_at(timestamp_s)
        link = satellite_link_state(
            timestamp_s=timestamp_s,
            ground_station_id=user.user_id,
            ground_position=position,
            satellite_position_ecef=CartesianPoint(
                x_m=state.position_ecef_m[0],
                y_m=state.position_ecef_m[1],
                z_m=state.position_ecef_m[2],
            ),
            satellite_velocity_ecef=CartesianPoint(
                x_m=state.velocity_ecef_m_s[0],
                y_m=state.velocity_ecef_m_s[1],
                z_m=state.velocity_ecef_m_s[2],
            ),
            carrier_frequency_hz=carrier_frequency_hz,
            bandwidth_hz=bandwidth_hz,
            tx_power_dbm=tx_power_dbm,
            tx_gain_dbi=tx_gain_dbi,
            rx_gain_dbi=rx_gain_dbi,
            noise_figure_db=noise_figure_db,
            propagation_losses=propagation_losses,
            interference_power_dbm=interference_power_dbm,
            required_sinr_db=required_sinr_db,
            minimum_elevation_deg=definition.minimum_elevation_deg,
            channel_model=channel_model,
            channel_link_id=f"{user.user_id}:{definition.satellite_id}",
        )
        candidates.append(
            SatelliteCandidate(
                satellite_id=definition.satellite_id,
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
