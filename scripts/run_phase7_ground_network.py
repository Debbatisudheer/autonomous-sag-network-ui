# ruff: noqa: I001
from __future__ import annotations

import json

from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.ground.association import evaluate_ground_network


ground_network = GroundNetwork(
    name="hyderabad-ground-baseline",
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
                atmospheric_db=1.0,
                rain_db=2.0,
                polarization_db=1.0,
                implementation_db=2.0,
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
                atmospheric_db=1.0,
                rain_db=2.0,
                polarization_db=1.0,
                implementation_db=2.0,
            ),
        ),
        GroundCell(
            cell_id="gnd-c",
            position=GeoPoint(latitude_deg=17.4450, longitude_deg=78.4700, altitude_m=545.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=43.0,
            tx_gain_dbi=14.0,
            noise_figure_db=5.0,
            required_sinr_db=8.0,
            maximum_service_distance_m=6_000.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=1.0,
                rain_db=2.0,
                polarization_db=1.0,
                implementation_db=2.0,
            ),
        ),
    ],
)

users = [
    MobileUser(
        user_id=f"user-{index:02d}",
        initial_position=GeoPoint(
            latitude_deg=17.385 + index * 0.006,
            longitude_deg=78.487 + index * 0.004,
            altitude_m=540.0,
        ),
        mobility=MobilityProfile(north_velocity_mps=8.0, east_velocity_mps=4.0),
    )
    for index in range(1, 7)
]

demands = {user.user_id: 20e6 for user in users}
snapshot = evaluate_ground_network(
    network=ground_network,
    users=users,
    demands_bps=demands,
    timestamp_s=60.0,
)

for association in snapshot.associations:
    print(json.dumps(association.model_dump(), indent=2))
