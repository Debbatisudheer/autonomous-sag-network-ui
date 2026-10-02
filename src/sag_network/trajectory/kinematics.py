from __future__ import annotations

import math
from bisect import bisect_left
from datetime import datetime, UTC

from sag_network.domain.models import GeoPoint
from sag_network.space.geodesy import geodetic_to_ecef
from sag_network.trajectory.models import (
    AerialTrajectory,
    AerialTrajectoryConfig,
    AerialTrajectoryState,
)


def _require_utc(timestamp_utc: datetime) -> datetime:
    if timestamp_utc.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    return timestamp_utc.astimezone(UTC)


def _local_velocity_mps(
    previous: GeoPoint, current: GeoPoint, dt_s: float
) -> tuple[float, float, float]:
    if dt_s <= 0:
        raise ValueError("trajectory sample interval must be positive")
    previous_ecef = geodetic_to_ecef(previous)
    current_ecef = geodetic_to_ecef(current)
    vx = (current_ecef.x_m - previous_ecef.x_m) / dt_s
    vy = (current_ecef.y_m - previous_ecef.y_m) / dt_s
    vz = (current_ecef.z_m - previous_ecef.z_m) / dt_s

    lat_rad = math.radians((previous.latitude_deg + current.latitude_deg) / 2.0)
    lon_rad = math.radians((previous.longitude_deg + current.longitude_deg) / 2.0)
    east_x = -math.sin(lon_rad)
    east_y = math.cos(lon_rad)
    north_x = -math.sin(lat_rad) * math.cos(lon_rad)
    north_y = -math.sin(lat_rad) * math.sin(lon_rad)
    north_z = math.cos(lat_rad)
    up_x = math.cos(lat_rad) * math.cos(lon_rad)
    up_y = math.cos(lat_rad) * math.sin(lon_rad)
    up_z = math.sin(lat_rad)
    east = east_x * vx + east_y * vy
    north = north_x * vx + north_y * vy + north_z * vz
    up = up_x * vx + up_y * vy + up_z * vz
    return north, east, up


def _zero_velocity(position: GeoPoint) -> tuple[float, float, float]:
    del position
    return 0.0, 0.0, 0.0


def _interpolate_position(left: GeoPoint, right: GeoPoint, ratio: float) -> GeoPoint:
    return GeoPoint(
        latitude_deg=left.latitude_deg + ratio * (right.latitude_deg - left.latitude_deg),
        longitude_deg=left.longitude_deg + ratio * (right.longitude_deg - left.longitude_deg),
        altitude_m=left.altitude_m + ratio * (right.altitude_m - left.altitude_m),
    )


def state_at(
    trajectory: AerialTrajectory,
    timestamp_utc: datetime,
    *,
    config: AerialTrajectoryConfig | None = None,
) -> AerialTrajectoryState:
    """Replay a trajectory at an exact sample or interpolate between adjacent observations."""
    effective_config = config or AerialTrajectoryConfig()
    timestamp = (
        _require_utc(timestamp_utc)
        if effective_config.require_timezone_aware
        else timestamp_utc
    )
    points = trajectory.points
    timestamps = [point.timestamp_utc for point in points]
    if timestamp < timestamps[0] or timestamp > timestamps[-1]:
        raise ValueError("timestamp_utc is outside the trajectory coverage interval")

    index = bisect_left(timestamps, timestamp)
    if index < len(points) and timestamps[index] == timestamp:
        if index == 0:
            north, east, up = _zero_velocity(points[index].position)
        else:
            previous = points[index - 1]
            current = points[index]
            dt_s = (current.timestamp_utc - previous.timestamp_utc).total_seconds()
            north, east, up = _local_velocity_mps(previous.position, current.position, dt_s)
        interpolated = False
        position = points[index].position
    else:
        right = points[index]
        left = points[index - 1]
        gap_s = (right.timestamp_utc - left.timestamp_utc).total_seconds()
        if gap_s > effective_config.maximum_interpolation_gap_s:
            raise ValueError("trajectory interpolation gap exceeds configured maximum")
        if not effective_config.allow_interpolation:
            raise ValueError(
                "trajectory timestamp is between observations and interpolation is disabled"
            )
        elapsed_s = (timestamp - left.timestamp_utc).total_seconds()
        ratio = elapsed_s / gap_s
        position = _interpolate_position(left.position, right.position, ratio)
        north, east, up = _local_velocity_mps(left.position, right.position, gap_s)
        interpolated = True

    speed = math.sqrt(north**2 + east**2 + up**2)
    course = math.degrees(math.atan2(east, north)) % 360.0 if speed > 1e-12 else 0.0
    return AerialTrajectoryState(
        trajectory_id=trajectory.trajectory_id,
        platform_id=trajectory.platform_id,
        platform_type=trajectory.platform_type,
        timestamp_utc=timestamp,
        position=position,
        velocity_north_mps=north,
        velocity_east_mps=east,
        velocity_up_mps=up,
        speed_mps=speed,
        course_deg=course,
        source_interpolated=interpolated,
    )
