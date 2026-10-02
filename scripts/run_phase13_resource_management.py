# ruff: noqa: I001
from __future__ import annotations

import json

from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.domain.resource import SpectrumResource
from sag_network.domain.traffic import QoSProfile, ServiceClass, TrafficDemand
from sag_network.domain.unified import SatelliteRadioProfile, UnifiedNetwork
from sag_network.resource.scheduler import schedule_spectrum
from sag_network.unified.association import evaluate_unified_network


LOSSES_GROUND = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=2.0,
    polarization_db=1.0,
    implementation_db=2.0,
)
LOSSES_AIR = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=1.0,
    polarization_db=1.0,
    implementation_db=2.0,
)
LOSSES_SPACE = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=0.5,
    polarization_db=0.5,
    implementation_db=1.0,
)


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
            propagation_losses=LOSSES_GROUND,
            scheduler_efficiency=0.75,
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
            propagation_losses=LOSSES_GROUND,
            scheduler_efficiency=0.75,
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
            propagation_losses=LOSSES_AIR,
            initial_energy_wh=100.0,
            reserve_energy_wh=20.0,
            hotel_power_w=40.0,
            propulsion_power_w=80.0,
            scheduler_efficiency=0.75,
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
        propagation_losses=LOSSES_SPACE,
        required_sinr_db=8.0,
    ),
)

users = [
    MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=17.391, longitude_deg=78.491, altitude_m=540.0),
        mobility=MobilityProfile(north_velocity_mps=4.0, east_velocity_mps=2.0),
    ),
    MobileUser(
        user_id="user-02",
        initial_position=GeoPoint(latitude_deg=17.405, longitude_deg=78.499, altitude_m=540.0),
        mobility=MobilityProfile(north_velocity_mps=3.0, east_velocity_mps=1.0),
    ),
]

snapshot = evaluate_unified_network(
    network=network,
    users=users,
    demands_bps={user.user_id: 0.0 for user in users},
    timestamp_s=180.0,
)

resources = {
    cell.cell_id: SpectrumResource(
        resource_id=cell.cell_id,
        bandwidth_hz=cell.bandwidth_hz,
        resource_block_bandwidth_hz=1e6,
        scheduler_efficiency=cell.scheduler_efficiency,
    )
    for cell in ground_network.cells
}
resources.update(
    {
        platform.platform_id: SpectrumResource(
            resource_id=platform.platform_id,
            bandwidth_hz=platform.bandwidth_hz,
            resource_block_bandwidth_hz=1e6,
            scheduler_efficiency=platform.scheduler_efficiency,
        )
        for platform in air_network.platforms
    }
)
resources.update(
    {
        satellite.satellite_id: SpectrumResource(
            resource_id=satellite.satellite_id,
            bandwidth_hz=network.satellite_radio.bandwidth_hz,
            resource_block_bandwidth_hz=1e6,
            scheduler_efficiency=0.75,
        )
        for satellite in constellation.satellites
    }
)

candidates_by_user = {
    association.user_id: association.candidates for association in snapshot.associations
}
demands = [
    TrafficDemand(
        flow_id="flow-high",
        user_id="user-01",
        demand_bps=60e6,
        qos=QoSProfile(
            service_class=ServiceClass.STREAMING,
            minimum_throughput_bps=20e6,
            maximum_latency_ms=100.0,
            maximum_loss_rate=0.02,
            priority=90,
        ),
    ),
    TrafficDemand(
        flow_id="flow-low",
        user_id="user-01",
        demand_bps=30e6,
        qos=QoSProfile(
            service_class=ServiceClass.BEST_EFFORT,
            minimum_throughput_bps=10e6,
            maximum_latency_ms=150.0,
            maximum_loss_rate=0.05,
            priority=10,
        ),
    ),
    TrafficDemand(
        flow_id="flow-user-02",
        user_id="user-02",
        demand_bps=30e6,
        qos=QoSProfile(
            service_class=ServiceClass.INTERACTIVE,
            minimum_throughput_bps=20e6,
            maximum_latency_ms=100.0,
            maximum_loss_rate=0.02,
            priority=50,
        ),
    ),
]

result = schedule_spectrum(
    timestamp_s=180.0,
    demands=demands,
    candidates_by_user=candidates_by_user,
    resources=resources,
)

print(json.dumps(result.model_dump(mode="json"), indent=2))
