from __future__ import annotations

import pytest

from sag_network.domain.handover import HandoverEventType
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.space.connectivity import user_satellite_candidates
from sag_network.space.handover import HandoverController
from sag_network.space.selection import SatelliteCandidate


def test_stationary_user_keeps_position() -> None:
    user = MobileUser(
        user_id="u1",
        initial_position=GeoPoint(latitude_deg=17.0, longitude_deg=78.0, altitude_m=500.0),
    )
    assert user.position_at(600.0) == user.initial_position


def test_northward_motion_increases_latitude() -> None:
    user = MobileUser(
        user_id="u1",
        initial_position=GeoPoint(latitude_deg=17.0, longitude_deg=78.0, altitude_m=500.0),
        mobility=MobilityProfile(north_velocity_mps=100.0),
    )
    later = user.position_at(60.0)
    assert later.latitude_deg > user.initial_position.latitude_deg
    assert later.longitude_deg == pytest.approx(78.0)


def test_eastward_motion_changes_longitude_without_large_latitude_change() -> None:
    user = MobileUser(
        user_id="u1",
        initial_position=GeoPoint(latitude_deg=17.0, longitude_deg=78.0, altitude_m=500.0),
        mobility=MobilityProfile(east_velocity_mps=100.0),
    )
    later = user.position_at(60.0)
    assert later.longitude_deg > user.initial_position.longitude_deg
    assert later.latitude_deg == pytest.approx(17.0, abs=1e-8)


def candidate(satellite_id: str, available: bool, margin: float) -> SatelliteCandidate:
    return SatelliteCandidate(
        satellite_id=satellite_id,
        available=available,
        link_margin_db=margin,
        elevation_deg=30.0,
        shannon_capacity_bps=100e6,
        propagation_delay_ms=5.0,
        doppler_shift_hz=1000.0,
    )


def test_handover_controller_initial_attach() -> None:
    controller = HandoverController(hysteresis_db=2.0, time_to_trigger_s=5.0)
    event = controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("sat-a", True, 8.0)],
    )
    assert event.event_type is HandoverEventType.ATTACH
    assert controller.serving_satellite_id == "sat-a"


def test_handover_requires_hysteresis_and_time_to_trigger() -> None:
    controller = HandoverController(hysteresis_db=2.0, time_to_trigger_s=10.0)
    controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("sat-a", True, 8.0)],
    )
    first = controller.update(
        user_id="u1",
        timestamp_s=5.0,
        candidates=[candidate("sat-a", True, 8.0), candidate("sat-b", True, 11.0)],
    )
    second = controller.update(
        user_id="u1",
        timestamp_s=15.0,
        candidates=[candidate("sat-a", True, 8.0), candidate("sat-b", True, 11.0)],
    )
    assert first.event_type is HandoverEventType.RETAIN
    assert second.event_type is HandoverEventType.HANDOVER
    assert controller.serving_satellite_id == "sat-b"


def test_handover_does_not_switch_below_hysteresis() -> None:
    controller = HandoverController(hysteresis_db=2.0, time_to_trigger_s=0.0)
    controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("sat-a", True, 8.0)],
    )
    event = controller.update(
        user_id="u1",
        timestamp_s=1.0,
        candidates=[candidate("sat-a", True, 8.0), candidate("sat-b", True, 9.0)],
    )
    assert event.event_type is HandoverEventType.RETAIN
    assert controller.serving_satellite_id == "sat-a"


def test_handover_moves_immediately_when_serving_link_fails() -> None:
    controller = HandoverController(hysteresis_db=2.0, time_to_trigger_s=10.0)
    controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("sat-a", True, 8.0), candidate("sat-b", True, 7.0)],
    )
    event = controller.update(
        user_id="u1",
        timestamp_s=60.0,
        candidates=[candidate("sat-a", False, -1.0), candidate("sat-b", True, 7.0)],
    )
    assert event.event_type is HandoverEventType.HANDOVER
    assert event.previous_satellite_id == "sat-a"
    assert event.new_satellite_id == "sat-b"


def test_no_coverage_preserves_previous_serving_id_in_event() -> None:
    controller = HandoverController(hysteresis_db=2.0, time_to_trigger_s=10.0)
    controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("sat-a", True, 8.0)],
    )
    event = controller.update(
        user_id="u1",
        timestamp_s=60.0,
        candidates=[candidate("sat-a", False, -1.0)],
    )
    assert event.event_type is HandoverEventType.NO_COVERAGE
    assert event.previous_satellite_id == "sat-a"
    assert controller.serving_satellite_id is None


def test_user_satellite_candidates_follow_current_user_position() -> None:
    from sag_network.domain.constellation import Constellation, SatelliteDefinition
    from sag_network.domain.link import PropagationLosses

    base_radius_m = 6_378_137.0 + 550_000.0
    constellation = Constellation(
        name="test",
        satellites=[
            SatelliteDefinition(
                satellite_id="sat-a",
                orbital_elements={
                    "semi_major_axis_m": base_radius_m,
                    "eccentricity": 0.0,
                    "inclination_deg": 53.0,
                    "raan_deg": 75.0,
                    "argument_of_perigee_deg": 0.0,
                    "mean_anomaly_deg": 0.0,
                },
            )
        ],
    )
    user = MobileUser(
        user_id="u1",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.4867, altitude_m=540.0),
        mobility=MobilityProfile(north_velocity_mps=10.0),
    )
    candidates = user_satellite_candidates(
        constellation=constellation,
        user=user,
        timestamp_s=60.0,
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=1.0, rain_db=0.5, polarization_db=0.5, implementation_db=1.0
        ),
        required_sinr_db=8.0,
    )
    assert len(candidates) == 1
    assert candidates[0].satellite_id == "sat-a"
    assert candidates[0].elevation_deg != 0.0


def test_inactive_user_has_no_satellite_candidates() -> None:
    from sag_network.domain.constellation import Constellation, SatelliteDefinition
    from sag_network.domain.link import PropagationLosses

    base_radius_m = 6_378_137.0 + 550_000.0
    constellation = Constellation(
        name="test",
        satellites=[
            SatelliteDefinition(
                satellite_id="sat-a",
                orbital_elements={
                    "semi_major_axis_m": base_radius_m,
                    "eccentricity": 0.0,
                    "inclination_deg": 53.0,
                    "raan_deg": 75.0,
                    "argument_of_perigee_deg": 0.0,
                    "mean_anomaly_deg": 0.0,
                },
            )
        ],
    )
    user = MobileUser(
        user_id="u1",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.4867, altitude_m=540.0),
        active=False,
    )
    assert user_satellite_candidates(
        constellation=constellation,
        user=user,
        timestamp_s=0.0,
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=1.0, rain_db=0.5, polarization_db=0.5, implementation_db=1.0
        ),
        required_sinr_db=8.0,
    ) == []
