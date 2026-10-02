from __future__ import annotations

import json

from sag_network.domain.link import PropagationLosses
from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.space.link import satellite_link_state
from sag_network.space.orbit import propagate_satellite_state

ground = GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=540)
elements = OrbitalElements(
    semi_major_axis_m=6_378_137.0 + 550_000.0,
    eccentricity=0.001,
    inclination_deg=53.0,
    raan_deg=20.0,
    argument_of_perigee_deg=15.0,
    mean_anomaly_deg=110.0,
)
losses = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=0.0,
    polarization_db=0.5,
    implementation_db=1.0,
)

for timestamp_s in (23170.0, 23230.0, 23290.0):
    state = propagate_satellite_state(elements, timestamp_s)
    result = satellite_link_state(
        timestamp_s=timestamp_s,
        ground_station_id="hyd-001",
        ground_position=ground,
        satellite_position_ecef=state.position_ecef,
        satellite_velocity_ecef=state.velocity_ecef,
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=losses,
        required_sinr_db=8.0,
        minimum_elevation_deg=10.0,
    )
    print(json.dumps(result, indent=2))
