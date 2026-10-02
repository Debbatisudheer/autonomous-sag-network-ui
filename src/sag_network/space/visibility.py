from __future__ import annotations

import math

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import CartesianPoint, GroundSatelliteVisibility
from sag_network.space.geodesy import geodetic_to_ecef, subtract, vector_norm_m


def _topocentric_enu(observer: GeoPoint, delta_ecef: CartesianPoint) -> tuple[float, float, float]:
    lat = math.radians(observer.latitude_deg)
    lon = math.radians(observer.longitude_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)

    east = -sin_lon * delta_ecef.x_m + cos_lon * delta_ecef.y_m
    north = (
        -sin_lat * cos_lon * delta_ecef.x_m
        - sin_lat * sin_lon * delta_ecef.y_m
        + cos_lat * delta_ecef.z_m
    )
    up = (
        cos_lat * cos_lon * delta_ecef.x_m
        + cos_lat * sin_lon * delta_ecef.y_m
        + sin_lat * delta_ecef.z_m
    )
    return east, north, up


def ground_to_satellite_visibility(
    *,
    timestamp_s: float,
    ground_station_id: str,
    ground_position: GeoPoint,
    satellite_position_ecef: CartesianPoint,
    minimum_elevation_deg: float = 10.0,
) -> GroundSatelliteVisibility:
    """Calculate slant range and elevation angle for a ground-to-satellite link."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")
    if not 0.0 <= minimum_elevation_deg <= 90.0:
        raise ValueError("minimum_elevation_deg must be between 0 and 90")

    observer_ecef = geodetic_to_ecef(ground_position)
    delta = subtract(satellite_position_ecef, observer_ecef)
    slant_range = vector_norm_m(delta)
    east, north, up = _topocentric_enu(ground_position, delta)
    horizontal_range = math.hypot(east, north)
    elevation_deg = math.degrees(math.atan2(up, horizontal_range))

    return GroundSatelliteVisibility(
        timestamp_s=timestamp_s,
        ground_station_id=ground_station_id,
        elevation_deg=elevation_deg,
        slant_range_m=slant_range,
        visible=elevation_deg >= minimum_elevation_deg,
    )
