from sag_network.domain.link import PropagationLosses
from sag_network.domain.models import GeoPoint
from sag_network.domain.space import CartesianPoint
from sag_network.space.link import satellite_link_state


def _losses() -> PropagationLosses:
    return PropagationLosses(
        atmospheric_db=1.0,
        rain_db=0.0,
        polarization_db=0.5,
        implementation_db=1.0,
    )


def test_visible_strong_satellite_link_is_available() -> None:
    ground = GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0)
    satellite = CartesianPoint(x_m=6_378_137.0 + 550_000.0, y_m=0.0, z_m=0.0)
    state = satellite_link_state(
        timestamp_s=0.0,
        ground_station_id="test-ground",
        ground_position=ground,
        satellite_position_ecef=satellite,
        satellite_velocity_ecef=CartesianPoint(x_m=0.0, y_m=7600.0, z_m=0.0),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=_losses(),
        required_sinr_db=8.0,
        minimum_elevation_deg=10.0,
    )
    assert state["visible"] is True
    assert state["available"] is True
    assert state["link_margin_db"] > 0


def test_geometrically_visible_but_insufficient_link_margin_is_unavailable() -> None:
    ground = GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0)
    satellite = CartesianPoint(x_m=6_378_137.0 + 550_000.0, y_m=0.0, z_m=0.0)
    state = satellite_link_state(
        timestamp_s=0.0,
        ground_station_id="test-ground",
        ground_position=ground,
        satellite_position_ecef=satellite,
        satellite_velocity_ecef=CartesianPoint(x_m=0.0, y_m=7600.0, z_m=0.0),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=0.0,
        tx_gain_dbi=0.0,
        rx_gain_dbi=0.0,
        noise_figure_db=5.0,
        propagation_losses=_losses(),
        required_sinr_db=8.0,
        minimum_elevation_deg=10.0,
    )
    assert state["visible"] is True
    assert state["available"] is False
    assert state["link_margin_db"] < 0
