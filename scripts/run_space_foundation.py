from __future__ import annotations

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.visibility import ground_to_satellite_visibility

ground = GeoPoint(latitude_deg=12.9716, longitude_deg=77.5946, altitude_m=920)
elements = OrbitalElements(
    semi_major_axis_m=6_378_137.0 + 550_000.0,
    eccentricity=0.001,
    inclination_deg=13.0,
    raan_deg=-12.4054,
    argument_of_perigee_deg=90.0,
    mean_anomaly_deg=5.0,
)

for timestamp_s in (0.0, 60.0, 120.0):
    state = propagate_satellite_state(elements, timestamp_s)
    visibility = ground_to_satellite_visibility(
        timestamp_s=timestamp_s,
        ground_station_id="ground-001",
        ground_position=ground,
        satellite_position_ecef=state.position_ecef,
        minimum_elevation_deg=10.0,
    )
    print(
        {
            "timestamp_s": timestamp_s,
            "satellite_eci_m": state.position_eci.model_dump(),
            "satellite_ecef_m": state.position_ecef.model_dump(),
            "elevation_deg": visibility.elevation_deg,
            "slant_range_m": visibility.slant_range_m,
            "visible": visibility.visible,
        }
    )
