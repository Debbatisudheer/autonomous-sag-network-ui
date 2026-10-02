from __future__ import annotations

import math

from sag_network.domain.space import CartesianPoint, OrbitalElements, SatelliteState

EARTH_MU_M3_S2 = 3.986004418e14
EARTH_ROTATION_RATE_RAD_S = 7.2921151467e-5


def _solve_kepler(mean_anomaly_rad: float, eccentricity: float) -> float:
    """Solve E - e*sin(E) = M with Newton-Raphson."""
    mean_anomaly_rad = (mean_anomaly_rad + math.pi) % (2.0 * math.pi) - math.pi
    estimate = mean_anomaly_rad if eccentricity < 0.8 else math.pi
    for _ in range(15):
        correction = (estimate - eccentricity * math.sin(estimate) - mean_anomaly_rad) / (
            1.0 - eccentricity * math.cos(estimate)
        )
        estimate -= correction
        if abs(correction) < 1e-13:
            return estimate
    raise RuntimeError("Kepler solver did not converge")


def _perifocal_to_eci_matrix(elements: OrbitalElements) -> tuple[tuple[float, ...], ...]:
    """Return the 3-1-3 rotation matrix from perifocal to ECI coordinates."""
    cos_raan = math.cos(math.radians(elements.raan_deg))
    sin_raan = math.sin(math.radians(elements.raan_deg))
    cos_i = math.cos(math.radians(elements.inclination_deg))
    sin_i = math.sin(math.radians(elements.inclination_deg))
    cos_arg = math.cos(math.radians(elements.argument_of_perigee_deg))
    sin_arg = math.sin(math.radians(elements.argument_of_perigee_deg))

    r11 = cos_raan * cos_arg - sin_raan * sin_arg * cos_i
    r12 = -cos_raan * sin_arg - sin_raan * cos_arg * cos_i
    r21 = sin_raan * cos_arg + cos_raan * sin_arg * cos_i
    r22 = -sin_raan * sin_arg + cos_raan * cos_arg * cos_i
    r31 = sin_arg * sin_i
    r32 = cos_arg * sin_i

    return ((r11, r12), (r21, r22), (r31, r32))


def _rotate_perifocal_to_eci(
    x_perifocal: float, y_perifocal: float, matrix: tuple[tuple[float, ...], ...]
) -> CartesianPoint:
    return CartesianPoint(
        x_m=matrix[0][0] * x_perifocal + matrix[0][1] * y_perifocal,
        y_m=matrix[1][0] * x_perifocal + matrix[1][1] * y_perifocal,
        z_m=matrix[2][0] * x_perifocal + matrix[2][1] * y_perifocal,
    )


def propagate_keplerian_eci(elements: OrbitalElements, timestamp_s: float) -> CartesianPoint:
    """Propagate an elliptic two-body orbit into the Earth-centered inertial frame."""
    return propagate_keplerian_state_eci(elements, timestamp_s)[0]


def propagate_keplerian_state_eci(
    elements: OrbitalElements, timestamp_s: float
) -> tuple[CartesianPoint, CartesianPoint]:
    """Propagate a two-body orbit and return ECI position and velocity."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")

    semi_major_axis = elements.semi_major_axis_m
    eccentricity = elements.eccentricity
    mean_motion = math.sqrt(EARTH_MU_M3_S2 / semi_major_axis**3)
    mean_anomaly = math.radians(elements.mean_anomaly_deg) + mean_motion * timestamp_s
    eccentric_anomaly = _solve_kepler(mean_anomaly, eccentricity)

    cos_e = math.cos(eccentric_anomaly)
    sin_e = math.sin(eccentric_anomaly)
    radius = semi_major_axis * (1.0 - eccentricity * cos_e)

    x_p = semi_major_axis * (cos_e - eccentricity)
    y_p = semi_major_axis * math.sqrt(1.0 - eccentricity**2) * sin_e

    denominator = 1.0 - eccentricity * cos_e
    xdot_p = -semi_major_axis * mean_motion * sin_e / denominator
    ydot_p = (
        semi_major_axis
        * mean_motion
        * math.sqrt(1.0 - eccentricity**2)
        * cos_e
        / denominator
    )

    matrix = _perifocal_to_eci_matrix(elements)
    position_eci = _rotate_perifocal_to_eci(x_p, y_p, matrix)
    velocity_eci = _rotate_perifocal_to_eci(xdot_p, ydot_p, matrix)

    computed_radius = math.sqrt(
        position_eci.x_m**2 + position_eci.y_m**2 + position_eci.z_m**2
    )
    if not math.isclose(computed_radius, radius, rel_tol=0.0, abs_tol=1e-3):
        raise RuntimeError("inconsistent propagated orbital radius")

    return position_eci, velocity_eci


def eci_to_ecef(
    position_eci: CartesianPoint,
    timestamp_s: float,
    initial_gmst_deg: float = 0.0,
) -> CartesianPoint:
    """Rotate an ECI position into ECEF using an Earth-rotation model."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")
    theta = math.radians(initial_gmst_deg) + EARTH_ROTATION_RATE_RAD_S * timestamp_s
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    x = cos_theta * position_eci.x_m + sin_theta * position_eci.y_m
    y = -sin_theta * position_eci.x_m + cos_theta * position_eci.y_m
    return CartesianPoint(x_m=x, y_m=y, z_m=position_eci.z_m)


def eci_velocity_to_ecef(
    position_eci: CartesianPoint,
    velocity_eci: CartesianPoint,
    timestamp_s: float,
    initial_gmst_deg: float = 0.0,
) -> CartesianPoint:
    """Convert inertial velocity to the rotating Earth-fixed frame."""
    position_ecef = eci_to_ecef(position_eci, timestamp_s, initial_gmst_deg)
    velocity_rotated = eci_to_ecef(velocity_eci, timestamp_s, initial_gmst_deg)
    omega_cross_r = CartesianPoint(
        x_m=-EARTH_ROTATION_RATE_RAD_S * position_ecef.y_m,
        y_m=EARTH_ROTATION_RATE_RAD_S * position_ecef.x_m,
        z_m=0.0,
    )
    return CartesianPoint(
        x_m=velocity_rotated.x_m - omega_cross_r.x_m,
        y_m=velocity_rotated.y_m - omega_cross_r.y_m,
        z_m=velocity_rotated.z_m,
    )


def propagate_satellite_state(
    elements: OrbitalElements,
    timestamp_s: float,
    initial_gmst_deg: float = 0.0,
) -> SatelliteState:
    """Return ECI/ECEF position and velocity for a simulation time."""
    position_eci, velocity_eci = propagate_keplerian_state_eci(elements, timestamp_s)
    position_ecef = eci_to_ecef(position_eci, timestamp_s, initial_gmst_deg)
    velocity_ecef = eci_velocity_to_ecef(
        position_eci, velocity_eci, timestamp_s, initial_gmst_deg
    )
    return SatelliteState(
        timestamp_s=timestamp_s,
        position_eci=position_eci,
        position_ecef=position_ecef,
        velocity_eci=velocity_eci,
        velocity_ecef=velocity_ecef,
    )
