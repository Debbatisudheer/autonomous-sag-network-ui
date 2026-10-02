from __future__ import annotations

from datetime import datetime, UTC

from sag_network.domain.air import AirNetwork, AirPlatform
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobilityProfile
from sag_network.trajectory.kinematics import state_at
from sag_network.trajectory.models import (
    AerialRadioProfile,
    AerialTrajectoryConfig,
    AerialTrajectoryDataset,
)


def _simulation_timestamp(timestamp_utc: datetime, simulation_epoch_utc: datetime) -> float:
    return (timestamp_utc.astimezone(UTC) - simulation_epoch_utc.astimezone(UTC)).total_seconds()


def build_air_network_at(
    dataset: AerialTrajectoryDataset,
    *,
    timestamp_utc: datetime,
    radio_profile: AerialRadioProfile,
    propagation_losses: PropagationLosses,
    simulation_epoch_utc: datetime,
    trajectory_config: AerialTrajectoryConfig | None = None,
    network_name: str = "real-aerial-network",
) -> AirNetwork:
    """Project external trajectory states into the existing AirNetwork contract at one time."""
    timestamp_s = _simulation_timestamp(timestamp_utc, simulation_epoch_utc)
    if timestamp_s < 0:
        raise ValueError("timestamp_utc must not precede simulation_epoch_utc")

    platforms: list[AirPlatform] = []
    for trajectory in sorted(dataset.trajectories, key=lambda item: item.platform_id):
        state = state_at(trajectory, timestamp_utc, config=trajectory_config)
        platforms.append(
            AirPlatform(
                platform_id=trajectory.platform_id,
                platform_type=trajectory.platform_type,
                initial_position=state.position,
                mobility=MobilityProfile(),
                carrier_frequency_hz=radio_profile.carrier_frequency_hz,
                bandwidth_hz=radio_profile.bandwidth_hz,
                tx_power_dbm=radio_profile.tx_power_dbm,
                tx_gain_dbi=radio_profile.tx_gain_dbi,
                rx_gain_dbi=radio_profile.rx_gain_dbi,
                noise_figure_db=radio_profile.noise_figure_db,
                required_sinr_db=radio_profile.required_sinr_db,
                maximum_service_distance_m=radio_profile.maximum_service_distance_m,
                propagation_losses=propagation_losses,
                active=True,
                scheduler_efficiency=radio_profile.scheduler_efficiency,
                initial_energy_wh=radio_profile.initial_energy_wh,
                reserve_energy_wh=radio_profile.reserve_energy_wh,
                hotel_power_w=radio_profile.hotel_power_w,
                propulsion_power_w=radio_profile.propulsion_power_w,
            )
        )
    del timestamp_s
    return AirNetwork(name=network_name, platforms=platforms)
