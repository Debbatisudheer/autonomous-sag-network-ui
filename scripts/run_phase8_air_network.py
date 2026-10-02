# ruff: noqa: I001
from __future__ import annotations

import json

from sag_network.air.association import evaluate_air_network
from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint


air_network = AirNetwork(
    name="hyderabad-air-baseline",
    platforms=[
        AirPlatform(
            platform_id="uav-a",
            platform_type=AirPlatformType.UAV,
            initial_position=GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=1_000.0),
            mobility=MobilityProfile(north_velocity_mps=10.0, east_velocity_mps=5.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=33.0,
            tx_gain_dbi=10.0,
            rx_gain_dbi=8.0,
            noise_figure_db=5.0,
            required_sinr_db=8.0,
            maximum_service_distance_m=25_000.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=1.0,
                rain_db=1.0,
                polarization_db=1.0,
                implementation_db=2.0,
            ),
            initial_energy_wh=100.0,
            reserve_energy_wh=20.0,
            hotel_power_w=40.0,
            propulsion_power_w=80.0,
        ),
        AirPlatform(
            platform_id="haps-a",
            platform_type=AirPlatformType.HAPS,
            initial_position=GeoPoint(latitude_deg=17.3900, longitude_deg=78.4900, altitude_m=20_000.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=40.0,
            tx_gain_dbi=16.0,
            rx_gain_dbi=10.0,
            noise_figure_db=5.0,
            required_sinr_db=8.0,
            maximum_service_distance_m=100_000.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=2.0,
                rain_db=2.0,
                polarization_db=1.0,
                implementation_db=2.0,
            ),
            initial_energy_wh=5_000.0,
            reserve_energy_wh=500.0,
            hotel_power_w=500.0,
        ),
    ],
)

users = [
    MobileUser(
        user_id=f"user-{index:02d}",
        initial_position=GeoPoint(
            latitude_deg=17.385 + index * 0.004,
            longitude_deg=78.487 + index * 0.003,
            altitude_m=540.0,
        ),
        mobility=MobilityProfile(north_velocity_mps=5.0, east_velocity_mps=2.0),
    )
    for index in range(1, 5)
]

demands = {user.user_id: 20e6 for user in users}

for timestamp_s in (0.0, 300.0, 600.0):
    snapshot = evaluate_air_network(
        network=air_network,
        users=users,
        demands_bps=demands,
        timestamp_s=timestamp_s,
    )
    print(json.dumps(snapshot.model_dump(), indent=2))
