from __future__ import annotations

import json

from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.domain.unified import SatelliteRadioProfile, UnifiedNetwork
from sag_network.domain.unified_handover import UnifiedHandoverPolicy
from sag_network.unified.cross_domain import run_cross_domain_mobility
from sag_network.unified.handover import UnifiedHandoverController

LOSSES = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=1.0,
    polarization_db=1.0,
    implementation_db=2.0,
)


def build_demo_network() -> UnifiedNetwork:
    ground = GroundNetwork(
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
                propagation_losses=LOSSES,
            )
        ],
    )
    air = AirNetwork(
        name="hyderabad-air",
        platforms=[
            AirPlatform(
                platform_id="uav-a",
                platform_type=AirPlatformType.UAV,
                initial_position=GeoPoint(
                    latitude_deg=17.3950, longitude_deg=78.4900, altitude_m=1_000.0
                ),
                mobility=MobilityProfile(north_velocity_mps=0.0, east_velocity_mps=0.0),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=33.0,
                tx_gain_dbi=10.0,
                rx_gain_dbi=8.0,
                noise_figure_db=5.0,
                required_sinr_db=8.0,
                maximum_service_distance_m=25_000.0,
                propagation_losses=LOSSES,
                initial_energy_wh=5.0,
                reserve_energy_wh=1.0,
                hotel_power_w=40.0,
                propulsion_power_w=0.0,
            )
        ],
    )
    radius = 6_378_137.0 + 550_000.0
    space = Constellation(
        name="hyderabad-leo",
        satellites=[
            SatelliteDefinition(
                satellite_id="leo-a",
                orbital_elements={
                    "semi_major_axis_m": radius,
                    "eccentricity": 0.0,
                    "inclination_deg": 53.0,
                    "raan_deg": 75.0,
                    "argument_of_perigee_deg": 0.0,
                    "mean_anomaly_deg": 0.0,
                },
            )
        ],
    )
    return UnifiedNetwork(
        name="phase10-cross-domain",
        ground=ground,
        air=air,
        space=space,
        satellite_radio=SatelliteRadioProfile(
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=44.0,
            tx_gain_dbi=25.0,
            rx_gain_dbi=20.0,
            noise_figure_db=5.0,
            propagation_losses=LOSSES,
            required_sinr_db=8.0,
        ),
    )


network = build_demo_network()
user = MobileUser(
    user_id="user-01",
    initial_position=GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=540.0),
    mobility=MobilityProfile(north_velocity_mps=30.0, east_velocity_mps=0.0),
)
controller = UnifiedHandoverController(
    policy=UnifiedHandoverPolicy(hysteresis_db=2.0, time_to_trigger_s=10.0)
)

events = run_cross_domain_mobility(
    network=network,
    users=[user],
    demands_bps={"user-01": 20e6},
    timestamps_s=(0.0, 60.0, 120.0, 180.0, 240.0, 300.0, 360.0, 420.0, 480.0),
    controllers={"user-01": controller},
)

for event in events["user-01"]:
    print(json.dumps(event.model_dump(mode="json"), indent=2))
