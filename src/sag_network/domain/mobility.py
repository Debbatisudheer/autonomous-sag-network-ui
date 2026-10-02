from __future__ import annotations

import math

from pydantic import BaseModel, Field

from sag_network.domain.models import GeoPoint
from sag_network.space.geodesy import WGS84_E2, WGS84_SEMI_MAJOR_AXIS_M


class MobilityProfile(BaseModel):
    """Constant local tangent-plane ground mobility model."""

    north_velocity_mps: float = 0.0
    east_velocity_mps: float = 0.0
    vertical_velocity_mps: float = 0.0

    @property
    def horizontal_speed_mps(self) -> float:
        return math.hypot(self.north_velocity_mps, self.east_velocity_mps)


class MobileUser(BaseModel):
    """A ground user whose position evolves deterministically from a WGS84 start point."""

    user_id: str = Field(min_length=1)
    initial_position: GeoPoint
    mobility: MobilityProfile = Field(default_factory=MobilityProfile)
    active: bool = True

    def position_at(self, timestamp_s: float) -> GeoPoint:
        """Return the user's geodetic position at a simulation timestamp."""
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")

        lat0_rad = math.radians(self.initial_position.latitude_deg)
        altitude_m = self.initial_position.altitude_m + self.mobility.vertical_velocity_mps * timestamp_s
        if altitude_m < 0:
            raise ValueError("mobility model would move the user below the Earth surface")

        sin_lat = math.sin(lat0_rad)
        denominator = math.sqrt(1.0 - WGS84_E2 * sin_lat**2)
        meridian_radius_m = (
            WGS84_SEMI_MAJOR_AXIS_M
            * (1.0 - WGS84_E2)
            / denominator**3
        )

        north_m = self.mobility.north_velocity_mps * timestamp_s
        east_m = self.mobility.east_velocity_mps * timestamp_s
        latitude_rad = lat0_rad + north_m / (meridian_radius_m + self.initial_position.altitude_m)
        latitude_rad = max(-math.pi / 2.0, min(math.pi / 2.0, latitude_rad))

        latitude_for_longitude = (lat0_rad + latitude_rad) / 2.0
        sin_mid = math.sin(latitude_for_longitude)
        mid_denominator = math.sqrt(1.0 - WGS84_E2 * sin_mid**2)
        mid_prime_vertical_radius_m = WGS84_SEMI_MAJOR_AXIS_M / mid_denominator
        longitude_delta_rad = east_m / (
            (mid_prime_vertical_radius_m + self.initial_position.altitude_m)
            * max(math.cos(latitude_for_longitude), 1e-12)
        )
        longitude_rad = math.radians(self.initial_position.longitude_deg) + longitude_delta_rad
        longitude_deg = ((math.degrees(longitude_rad) + 180.0) % 360.0) - 180.0

        return GeoPoint(
            latitude_deg=math.degrees(latitude_rad),
            longitude_deg=longitude_deg,
            altitude_m=altitude_m,
        )
