from __future__ import annotations

import json

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.space.link import satellite_link_state
from sag_network.space.orbit import propagate_satellite_state


def main() -> None:
    station = GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=0.0)
    elements = OrbitalElements(
        semi_major_axis_m=6_378_137.0 + 550_000.0,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=10.0,
        argument_of_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )

    for timestamp_s in (0.0, 60.0, 120.0):
        state = propagate_satellite_state(elements, timestamp_s)
        link = satellite_link_state(
            timestamp_s=timestamp_s,
            ground_station_id="hyd-001",
            ground_position=station,
            satellite_position_ecef=state.position_ecef,
            satellite_velocity_ecef=state.velocity_ecef,
            carrier_frequency_hz=2.0e9,
            tx_power_dbm=30.0,
            tx_gain_dbi=20.0,
            rx_gain_dbi=2.0,
            minimum_elevation_deg=10.0,
        )
        print(json.dumps(link, indent=2))


if __name__ == "__main__":
    main()
