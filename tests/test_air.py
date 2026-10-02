from __future__ import annotations

import pytest

from sag_network.air.association import evaluate_air_network
from sag_network.air.link import air_user_link_state
from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint


def make_uav(**overrides: object) -> AirPlatform:
    values: dict[str, object] = {
        "platform_id": "uav-a",
        "platform_type": AirPlatformType.UAV,
        "initial_position": GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=1_000),
        "mobility": MobilityProfile(north_velocity_mps=10.0, east_velocity_mps=5.0),
        "carrier_frequency_hz": 3.5e9,
        "bandwidth_hz": 20e6,
        "tx_power_dbm": 33.0,
        "tx_gain_dbi": 10.0,
        "rx_gain_dbi": 8.0,
        "noise_figure_db": 5.0,
        "required_sinr_db": 8.0,
        "maximum_service_distance_m": 25_000.0,
        "propagation_losses": PropagationLosses(
            atmospheric_db=1.0,
            rain_db=1.0,
            polarization_db=1.0,
            implementation_db=2.0,
        ),
        "initial_energy_wh": 100.0,
        "reserve_energy_wh": 20.0,
        "hotel_power_w": 40.0,
        "propulsion_power_w": 80.0,
    }
    values.update(overrides)
    return AirPlatform.model_validate(values)


def make_haps() -> AirPlatform:
    return AirPlatform(
        platform_id="haps-a",
        platform_type=AirPlatformType.HAPS,
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=20_000),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=40.0,
        tx_gain_dbi=16.0,
        rx_gain_dbi=10.0,
        noise_figure_db=5.0,
        required_sinr_db=8.0,
        maximum_service_distance_m=100_000.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=2.0,
            rain_db=2.0,
            polarization_db=1.0,
            implementation_db=2.0,
        ),
        initial_energy_wh=5_000.0,
        reserve_energy_wh=500.0,
        hotel_power_w=500.0,
    )


def make_user() -> MobileUser:
    return MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
        mobility=MobilityProfile(north_velocity_mps=5.0, east_velocity_mps=2.0),
    )


def test_uav_position_changes_with_mobility() -> None:
    platform = make_uav()
    start = platform.position_at(0.0)
    later = platform.position_at(60.0)
    assert later.latitude_deg != start.latitude_deg
    assert later.longitude_deg != start.longitude_deg


def test_haps_baseline_is_stationary() -> None:
    platform = make_haps()
    start = platform.position_at(0.0)
    later = platform.position_at(600.0)
    assert later == start


def test_energy_decreases_over_time() -> None:
    platform = make_uav()
    assert platform.energy_remaining_wh(0.0) > platform.energy_remaining_wh(300.0)


def test_energy_reserve_time_is_positive_when_available() -> None:
    platform = make_uav()
    assert platform.time_to_reserve_s(0.0) is not None
    assert platform.time_to_reserve_s(0.0) > 0


def test_energy_exhaustion_disables_platform() -> None:
    platform = make_uav(initial_energy_wh=10.0, reserve_energy_wh=5.0)
    assert not platform.energy_available(200.0)


def test_energy_reserve_must_be_below_initial_energy() -> None:
    with pytest.raises(ValueError, match="reserve_energy_wh"):
        make_uav(initial_energy_wh=20.0, reserve_energy_wh=20.0)


def test_haps_rejects_horizontal_mobility() -> None:
    with pytest.raises(ValueError, match="HAPS baseline"):
        AirPlatform(
            **make_haps().model_dump(exclude={"mobility"}),
            mobility=MobilityProfile(north_velocity_mps=1.0),
        )


def test_air_link_is_available_within_range_and_energy() -> None:
    candidate = air_user_link_state(platform=make_uav(), user=make_user(), timestamp_s=0.0)
    assert candidate.available
    assert candidate.distance_m < 25_000.0
    assert candidate.remaining_energy_wh == pytest.approx(100.0)


def test_air_link_unavailable_beyond_service_range() -> None:
    platform = make_uav(maximum_service_distance_m=400.0)
    candidate = air_user_link_state(platform=platform, user=make_user(), timestamp_s=0.0)
    assert not candidate.available


def test_air_link_unavailable_at_energy_reserve() -> None:
    platform = make_uav(initial_energy_wh=20.0, reserve_energy_wh=10.0)
    candidate = air_user_link_state(platform=platform, user=make_user(), timestamp_s=330.0)
    assert not candidate.available


def test_air_network_association_is_deterministic() -> None:
    network = AirNetwork(name="air-baseline", platforms=[make_uav(), make_haps()])
    snapshot = evaluate_air_network(
        network=network,
        users=[make_user()],
        demands_bps={"user-01": 20e6},
        timestamp_s=0.0,
    )
    association = snapshot.associations[0]
    assert association.selected_platform_id in {"uav-a", "haps-a"}
    assert association.allocated_capacity_bps > 0


def test_multi_user_association_reports_all_users() -> None:
    network = AirNetwork(name="air-baseline", platforms=[make_uav(), make_haps()])
    users = [
        make_user(),
        MobileUser(
            user_id="user-02",
            initial_position=GeoPoint(latitude_deg=17.39, longitude_deg=78.49, altitude_m=540),
        ),
    ]
    snapshot = evaluate_air_network(
        network=network,
        users=users,
        demands_bps={"user-01": 20e6, "user-02": 20e6},
        timestamp_s=0.0,
    )
    assert [item.user_id for item in snapshot.associations] == ["user-01", "user-02"]
    assert all(item.allocated_capacity_bps > 0 for item in snapshot.associations)
