from __future__ import annotations

import math
from datetime import datetime, UTC

from sag_network.domain.space import CartesianPoint


J2000_JULIAN_DATE = 2_451_545.0
SECONDS_PER_DAY = 86_400.0
EARTH_ROTATION_RATE_RAD_S = 7.29211514670698e-5


def datetime_to_julian_date_parts(timestamp_utc: datetime) -> tuple[float, float]:
    """Return a Julian date split into whole and fractional-day parts."""
    if timestamp_utc.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    timestamp = timestamp_utc.astimezone(UTC)
    year = timestamp.year
    month = timestamp.month
    day = timestamp.day
    if month <= 2:
        year -= 1
        month += 12

    a = year // 100
    b = 2 - a + a // 4
    julian_day_number = (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + b
        - 1524
    )
    seconds_since_midnight = (
        timestamp.hour * 3_600.0
        + timestamp.minute * 60.0
        + timestamp.second
        + timestamp.microsecond / 1_000_000.0
    )
    julian_date_value = julian_day_number - 0.5 + seconds_since_midnight / SECONDS_PER_DAY
    whole = math.floor(julian_date_value)
    fraction = julian_date_value - whole
    return float(whole), float(fraction)


def julian_date(timestamp_utc: datetime) -> float:
    whole, fraction = datetime_to_julian_date_parts(timestamp_utc)
    return whole + fraction


def gmst_degrees(timestamp_utc: datetime) -> float:
    """Compute Greenwich mean sidereal time from the UTC Julian date."""
    jd = julian_date(timestamp_utc)
    centuries = (jd - J2000_JULIAN_DATE) / 36_525.0
    theta = (
        280.46061837
        + 360.98564736629 * (jd - J2000_JULIAN_DATE)
        + 0.000387933 * centuries**2
        - centuries**3 / 38_710_000.0
    )
    return theta % 360.0


def teme_to_ecef(
    position_teme_km: tuple[float, float, float], timestamp_utc: datetime
) -> CartesianPoint:
    """Convert TEME position to an Earth-fixed vector using GMST.

    Polar motion and UT1-UTC corrections are intentionally not applied in Phase 25.
    A later Earth-orientation integration can replace this frame adapter without
    changing the SGP4 provider contract.
    """
    theta = math.radians(gmst_degrees(timestamp_utc))
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    x_km, y_km, z_km = position_teme_km
    return CartesianPoint(
        x_m=(cos_theta * x_km + sin_theta * y_km) * 1_000.0,
        y_m=(-sin_theta * x_km + cos_theta * y_km) * 1_000.0,
        z_m=z_km * 1_000.0,
    )


def teme_velocity_to_ecef(
    position_teme_km: tuple[float, float, float],
    velocity_teme_km_s: tuple[float, float, float],
    timestamp_utc: datetime,
) -> CartesianPoint:
    """Convert TEME velocity to ECEF velocity using the GMST rotation."""
    theta = math.radians(gmst_degrees(timestamp_utc))
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    x_km, y_km, _ = position_teme_km
    vx_km_s, vy_km_s, vz_km_s = velocity_teme_km_s

    x_m = (cos_theta * x_km + sin_theta * y_km) * 1_000.0
    y_m = (-sin_theta * x_km + cos_theta * y_km) * 1_000.0
    vx_rot_m_s = (cos_theta * vx_km_s + sin_theta * vy_km_s) * 1_000.0
    vy_rot_m_s = (-sin_theta * vx_km_s + cos_theta * vy_km_s) * 1_000.0
    return CartesianPoint(
        x_m=vx_rot_m_s + EARTH_ROTATION_RATE_RAD_S * y_m,
        y_m=vy_rot_m_s - EARTH_ROTATION_RATE_RAD_S * x_m,
        z_m=vz_km_s * 1_000.0,
    )
