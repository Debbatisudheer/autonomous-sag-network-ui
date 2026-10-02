import math

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.space.geodesy import vector_norm_m
from sag_network.space.link import doppler_shift_hz, propagation_delay_ms, range_rate_mps
from sag_network.space.orbit import propagate_keplerian_state_eci, propagate_satellite_state


def _elements() -> OrbitalElements:
    return OrbitalElements(
        semi_major_axis_m=6_378_137.0 + 550_000.0,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=10.0,
        argument_of_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )


def test_circular_orbit_speed_is_physical_order() -> None:
    elements = OrbitalElements(
        semi_major_axis_m=6_378_137.0 + 550_000.0,
        eccentricity=0.0,
        inclination_deg=51.6,
        raan_deg=10.0,
        argument_of_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )
    _, velocity = propagate_keplerian_state_eci(elements, 0.0)
    speed = vector_norm_m(velocity)
    expected = math.sqrt(3.986004418e14 / elements.semi_major_axis_m)
    assert math.isclose(speed, expected, rel_tol=1e-12)


def test_ecef_velocity_includes_earth_rotation() -> None:
    state = propagate_satellite_state(_elements(), 120.0)
    assert not math.isclose(
        vector_norm_m(state.velocity_eci), vector_norm_m(state.velocity_ecef), rel_tol=0.0, abs_tol=1e-9
    )


def test_range_rate_is_derived_from_geometry_and_velocity() -> None:
    state = propagate_satellite_state(_elements(), 0.0)
    station = GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0)
    rate = range_rate_mps(state.position_ecef, state.velocity_ecef, station)
    assert math.isfinite(rate)
    assert abs(rate) < 8_000.0


def test_doppler_shift_scales_linearly() -> None:
    frequency = 2.0e9
    shift = doppler_shift_hz(frequency, 1_000.0)
    assert math.isclose(shift, -frequency * 1_000.0 / 299_792_458.0, rel_tol=1e-12)


def test_propagation_delay_matches_range() -> None:
    assert math.isclose(propagation_delay_ms(299_792.458), 1.0, rel_tol=1e-12)
