from __future__ import annotations

import math

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import CartesianPoint

WGS84_SEMI_MAJOR_AXIS_M = 6_378_137.0
WGS84_FLATTENING = 1.0 / 298.257223563
WGS84_E2 = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)


def geodetic_to_ecef(point: GeoPoint) -> CartesianPoint:
    """Convert geodetic latitude/longitude/height to WGS84 ECEF coordinates."""
    lat = math.radians(point.latitude_deg)
    lon = math.radians(point.longitude_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    prime_vertical_radius = WGS84_SEMI_MAJOR_AXIS_M / math.sqrt(1.0 - WGS84_E2 * sin_lat**2)

    x = (prime_vertical_radius + point.altitude_m) * cos_lat * math.cos(lon)
    y = (prime_vertical_radius + point.altitude_m) * cos_lat * math.sin(lon)
    z = (prime_vertical_radius * (1.0 - WGS84_E2) + point.altitude_m) * sin_lat
    return CartesianPoint(x_m=x, y_m=y, z_m=z)


def vector_norm_m(point: CartesianPoint) -> float:
    return math.sqrt(point.x_m**2 + point.y_m**2 + point.z_m**2)


def subtract(a: CartesianPoint, b: CartesianPoint) -> CartesianPoint:
    return CartesianPoint(x_m=a.x_m - b.x_m, y_m=a.y_m - b.y_m, z_m=a.z_m - b.z_m)
