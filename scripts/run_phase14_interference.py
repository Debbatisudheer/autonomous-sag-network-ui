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
from sag_network.interference.evaluator import apply_channel_effects_to_candidate
from sag_network.interference.model import ChannelEffectProfile, InterferenceSource
from sag_network.space.orbit import OrbitalElements
from sag_network.unified.association import evaluate_unified_network


LOSSES = PropagationLosses(
    atmospheric_db=0.3,
    rain_db=0.5,
    polarization_db=0.2,
    implementation_db=0.5,
)
GROUND = GroundNetwork(
    name="ground-demo",
    cells=[
        GroundCell(
            cell_id="gnd-a",
            position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=43,
            noise_figure_db=5,
            maximum_service_distance_m=50_000,
            propagation_losses=LOSSES,
        )
    ],
)
AIR = AirNetwork(
    name="air-demo",
    platforms=[
        AirPlatform(
            platform_id="uav-a",
            platform_type=AirPlatformType.UAV,
            initial_position=GeoPoint(latitude_deg=17.40, longitude_deg=78.49, altitude_m=500),
            mobility=MobilityProfile(horizontal_speed_mps=8.0, heading_deg=90.0),
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=43,
            noise_figure_db=5,
            maximum_service_distance_m=50_000,
            propagation_losses=LOSSES,
            initial_energy_wh=10_000,
            reserve_energy_wh=1_000,
            hotel_power_w=100,
            propulsion_power_w=350,
        )
    ],
)
SPACE = Constellation(
    name="leo-demo",
    satellites=[
        SatelliteDefinition(
            satellite_id="leo-a",
            orbital_elements=OrbitalElements(
                semi_major_axis_m=6_900_000,
                eccentricity=0.001,
                inclination_deg=53.0,
                raan_deg=0.0,
                argument_of_perigee_deg=0.0,
                mean_anomaly_deg=0.0,
            ),
        )
    ],
)
NETWORK = UnifiedNetwork(
    name="sag-phase14-demo",
    ground=GROUND,
    air=AIR,
    space=SPACE,
    satellite_radio=SatelliteRadioProfile(
        carrier_frequency_hz=2.0e9,
        bandwidth_hz=20e6,
        tx_power_dbm=43,
        tx_gain_dbi=5,
        rx_gain_dbi=5,
        noise_figure_db=4,
        propagation_losses=LOSSES,
        required_sinr_db=3.0,
    ),
)
USER = MobileUser(
    user_id="user-01",
    initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
)

snapshot = evaluate_unified_network(
    network=NETWORK,
    users=[USER],
    demands_bps={"user-01": 50e6},
    timestamp_s=180.0,
)
candidate = next(item for item in snapshot.associations[0].candidates if item.resource_id == "uav-a")

interferers = [
    InterferenceSource(
        source_id="gnd-interferer",
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        distance_m=2_500.0,
        tx_power_dbm=30.0,
        tx_gain_dbi=8.0,
        rx_gain_dbi=0.0,
        additional_path_loss_db=3.0,
        activity_factor=0.7,
    ),
    InterferenceSource(
        source_id="adjacent-interferer",
        carrier_frequency_hz=3.515e9,
        bandwidth_hz=10e6,
        distance_m=3_000.0,
        tx_power_dbm=27.0,
        tx_gain_dbi=6.0,
        additional_path_loss_db=5.0,
        coupling_loss_db=6.0,
        activity_factor=0.5,
    ),
]

affected = apply_channel_effects_to_candidate(
    candidate=candidate,
    carrier_frequency_hz=3.5e9,
    bandwidth_hz=20e6,
    required_sinr_db=5.0,
    channel_effects=ChannelEffectProfile(additional_loss_db=4.0),
    interferers=interferers,
)

print(json.dumps({
    "timestamp_s": snapshot.timestamp_s,
    "resource_id": candidate.resource_id,
    "baseline": {
        "rx_power_dbm": candidate.rx_power_dbm,
        "sinr_db": candidate.sinr_db,
        "capacity_bps": candidate.shannon_capacity_bps,
        "available": candidate.available,
    },
    "phase14": {
        "channel_additional_loss_db": 4.0,
        "rx_power_dbm": affected.rx_power_dbm,
        "sinr_db": affected.sinr_db,
        "capacity_bps": affected.shannon_capacity_bps,
        "estimated_capacity_bps": affected.estimated_capacity_bps,
        "link_margin_db": affected.link_margin_db,
        "available": affected.available,
    },
}, indent=2))
