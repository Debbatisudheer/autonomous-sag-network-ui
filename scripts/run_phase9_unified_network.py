# ruff: noqa: I001
from __future__ import annotations

import json

from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.domain.unified import SatelliteRadioProfile, UnifiedNetwork
from sag_network.unified.association import evaluate_unified_network


ground_network = GroundNetwork(
    name="hyderabad-ground",
    cells=[
        GroundCell(
            cell_id="gnd-a",
            position=GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=540.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=43.0,
            tx_gain_dbi=14.0,
            noise_figure_db=5.0,
            required_sinr_db=8.0,
            maximum_service_distance_m=6_000.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=1.0, rain_db=2.0, polarization_db=1.0, implementation_db=2.0
            ),
        ),
        GroundCell(
            cell_id="gnd-b",
            position=GeoPoint(latitude_deg=17.4200, longitude_deg=78.5000, altitude_m=550.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=43.0,
            tx_gain_dbi=14.0,
            noise_figure_db=5.0,
            required_sinr_db=8.0,
            maximum_service_distance_m=6_000.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=1.0, rain_db=2.0, polarization_db=1.0, implementation_db=2.0
            ),
        ),
    ],
)

air_network = AirNetwork(
    name="hyderabad-air",
    platforms=[
        AirPlatform(
            platform_id="uav-a",
            platform_type=AirPlatformType.UAV,
            initial_position=GeoPoint(latitude_deg=17.4000, longitude_deg=78.4950, altitude_m=1_000.0),
            mobility=MobilityProfile(north_velocity_mps=3.0, east_velocity_mps=1.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=33.0,
            tx_gain_dbi=10.0,
            rx_gain_dbi=8.0,
            noise_figure_db=5.0,
            required_sinr_db=8.0,
            maximum_service_distance_m=25_000.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=1.0, rain_db=1.0, polarization_db=1.0, implementation_db=2.0
            ),
            initial_energy_wh=100.0,
            reserve_energy_wh=20.0,
            hotel_power_w=40.0,
            propulsion_power_w=80.0,
        )
    ],
)

base_radius_m = 6_378_137.0 + 550_000.0
constellation = Constellation(
    name="hyderabad-leo",
    satellites=[
        SatelliteDefinition(
            satellite_id="leo-a",
            orbital_elements={
                "semi_major_axis_m": base_radius_m,
                "eccentricity": 0.0,
                "inclination_deg": 53.0,
                "raan_deg": 75.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 0.0,
            },
        ),
        SatelliteDefinition(
            satellite_id="leo-b",
            orbital_elements={
                "semi_major_axis_m": base_radius_m,
                "eccentricity": 0.0,
                "inclination_deg": 53.0,
                "raan_deg": 285.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 180.0,
            },
        ),
    ],
)

network = UnifiedNetwork(
    name="hyderabad-sag-baseline",
    ground=ground_network,
    air=air_network,
    space=constellation,
    satellite_radio=SatelliteRadioProfile(
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=1.0, rain_db=0.5, polarization_db=0.5, implementation_db=1.0
        ),
        required_sinr_db=8.0,
    ),
)

users = [
    MobileUser(
        user_id=f"user-{index:02d}",
        initial_position=GeoPoint(
            latitude_deg=17.385 + index * 0.006,
            longitude_deg=78.487 + index * 0.004,
            altitude_m=540.0,
        ),
        mobility=MobilityProfile(north_velocity_mps=4.0, east_velocity_mps=2.0),
    )
    for index in range(1, 5)
]

demands = {user.user_id: 20e6 for user in users}

for timestamp_s in (180.0, 600.0):
    snapshot = evaluate_unified_network(
        network=network,
        users=users,
        demands_bps=demands,
        timestamp_s=timestamp_s,
    )
    print(json.dumps(snapshot.model_dump(mode="json"), indent=2))
