# ruff: noqa: I001
from __future__ import annotations

import json

from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.handover import HandoverEventType
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.space.connectivity import user_satellite_candidates
from sag_network.space.handover import HandoverController


ground = GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=540.0)
base_radius_m = 6_378_137.0 + 550_000.0

constellation = Constellation(
    name="analytical-leo-mobility-demo",
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
                "raan_deg": 75.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 20.0,
            },
        ),
    ],
)

user = MobileUser(
    user_id="user-001",
    initial_position=ground,
    mobility=MobilityProfile(north_velocity_mps=12.0, east_velocity_mps=8.0),
)
losses = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=0.5,
    polarization_db=0.5,
    implementation_db=1.0,
)
controller = HandoverController(hysteresis_db=2.0, time_to_trigger_s=10.0)

for timestamp_s in range(0, 511, 30):
    position = user.position_at(float(timestamp_s))
    candidates = user_satellite_candidates(
        constellation=constellation,
        user=user,
        timestamp_s=float(timestamp_s),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=losses,
        required_sinr_db=8.0,
    )
    event = controller.update(
        user_id=user.user_id,
        timestamp_s=float(timestamp_s),
        candidates=candidates,
    )
    print(
        json.dumps(
            {
                "timestamp_s": float(timestamp_s),
                "user_position": position.model_dump(),
                "serving_satellite_id": controller.serving_satellite_id,
                "event_type": event.event_type.value,
                "event_reason": event.reason,
                "candidates": [candidate.__dict__ for candidate in candidates],
            },
            indent=2,
        )
    )
    if event.event_type in {HandoverEventType.ATTACH, HandoverEventType.HANDOVER, HandoverEventType.NO_COVERAGE}:
        continue
