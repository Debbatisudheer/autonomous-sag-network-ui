import math

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.space.geodesy import geodetic_to_ecef, vector_norm_m
from sag_network.space.orbit import eci_to_ecef, propagate_keplerian_eci, propagate_satellite_state
from sag_network.space.visibility import ground_to_satellite_visibility


def test_wgs84_equator_origin() -> None:
    point = geodetic_to_ecef(GeoPoint(latitude_deg=0, longitude_deg=0, altitude_m=0))
    assert math.isclose(point.x_m, 6_378_137.0, abs_tol=1e-6)
    assert math.isclose(point.y_m, 0.0, abs_tol=1e-6)
    assert math.isclose(point.z_m, 0.0, abs_tol=1e-6)


def test_circular_orbit_preserves_radius() -> None:
    elements = OrbitalElements(
        semi_major_axis_m=6_378_137.0 + 550_000.0,
        eccentricity=0.0,
        inclination_deg=51.6,
        raan_deg=10.0,
        argument_of_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )
    position = propagate_keplerian_eci(elements, 1234.0)
    assert math.isclose(
        vector_norm_m(position), elements.semi_major_axis_m, rel_tol=0, abs_tol=1e-3
    )


def test_earth_rotation_changes_ecef_longitudinal_frame() -> None:
    position = geodetic_to_ecef(GeoPoint(latitude_deg=0, longitude_deg=0, altitude_m=0))
    rotated = eci_to_ecef(position, 1_000.0)
    assert not math.isclose(rotated.x_m, position.x_m, abs_tol=1.0)
    assert not math.isclose(rotated.y_m, position.y_m, abs_tol=1.0)


def test_satellite_state_contains_consistent_frames() -> None:
    elements = OrbitalElements(
        semi_major_axis_m=6_378_137.0 + 550_000.0,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=10.0,
        argument_of_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )
    state = propagate_satellite_state(elements, 120.0)
    assert state.timestamp_s == 120.0
    assert math.isclose(
        vector_norm_m(state.position_eci), elements.semi_major_axis_m, rel_tol=0.001
    )


def test_satellite_above_horizon_is_visible() -> None:
    satellite = geodetic_to_ecef(
        GeoPoint(latitude_deg=0, longitude_deg=0, altitude_m=550_000)
    )
    visibility = ground_to_satellite_visibility(
        timestamp_s=0,
        ground_station_id="gs-001",
        ground_position=GeoPoint(latitude_deg=0, longitude_deg=0, altitude_m=0),
        satellite_position_ecef=satellite,
        minimum_elevation_deg=10,
    )
    assert visibility.visible
    assert visibility.elevation_deg > 80
    assert math.isclose(visibility.slant_range_m, 550_000, abs_tol=1.0)


def test_satellite_below_minimum_elevation_is_not_visible() -> None:
    satellite = geodetic_to_ecef(
        GeoPoint(latitude_deg=0, longitude_deg=20, altitude_m=550_000)
    )
    visibility = ground_to_satellite_visibility(
        timestamp_s=0,
        ground_station_id="gs-001",
        ground_position=GeoPoint(latitude_deg=0, longitude_deg=0, altitude_m=0),
        satellite_position_ecef=satellite,
        minimum_elevation_deg=10,
    )
    assert not visibility.visible
    assert visibility.elevation_deg < 10
