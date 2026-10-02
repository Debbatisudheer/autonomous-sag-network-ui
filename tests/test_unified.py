from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.models import GeoPoint
from sag_network.domain.unified import NetworkDomain, SatelliteRadioProfile, UnifiedNetwork
from sag_network.unified.association import evaluate_unified_network


LOSSES = PropagationLosses(
    atmospheric_db=1.0, rain_db=1.0, polarization_db=1.0, implementation_db=2.0
)


def build_network() -> UnifiedNetwork:
    ground = GroundNetwork(
        name="ground",
        cells=[
            GroundCell(
                cell_id="gnd-a",
                position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=43,
                tx_gain_dbi=14,
                noise_figure_db=5,
                required_sinr_db=8,
                maximum_service_distance_m=6_000,
                propagation_losses=LOSSES,
            )
        ],
    )
    air = AirNetwork(
        name="air",
        platforms=[
            AirPlatform(
                platform_id="uav-a",
                platform_type=AirPlatformType.UAV,
                initial_position=GeoPoint(
                    latitude_deg=17.385, longitude_deg=78.487, altitude_m=1_000
                ),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=33,
                tx_gain_dbi=10,
                rx_gain_dbi=8,
                noise_figure_db=5,
                required_sinr_db=8,
                maximum_service_distance_m=25_000,
                propagation_losses=LOSSES,
                initial_energy_wh=100,
                reserve_energy_wh=20,
                hotel_power_w=40,
                propulsion_power_w=80,
            )
        ],
    )
    orbit = {
        "semi_major_axis_m": 6_378_137.0 + 550_000.0,
        "eccentricity": 0.0,
        "inclination_deg": 53.0,
        "raan_deg": 75.0,
        "argument_of_perigee_deg": 0.0,
        "mean_anomaly_deg": 0.0,
    }
    space = Constellation(
        name="space",
        satellites=[SatelliteDefinition(satellite_id="leo-a", orbital_elements=orbit)],
    )
    return UnifiedNetwork(
        name="test",
        ground=ground,
        air=air,
        space=space,
        satellite_radio=SatelliteRadioProfile(
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=44,
            tx_gain_dbi=25,
            rx_gain_dbi=20,
            noise_figure_db=5,
            propagation_losses=LOSSES,
            required_sinr_db=8,
        ),
    )


def test_unified_network_merges_three_domains() -> None:
    network = build_network()
    user = MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
    )
    snapshot = evaluate_unified_network(
        network=network,
        users=[user],
        demands_bps={"user-01": 10e6},
        timestamp_s=0,
    )
    candidates = snapshot.associations[0].candidates
    assert {candidate.domain for candidate in candidates} == {
        NetworkDomain.GROUND,
        NetworkDomain.AIR,
        NetworkDomain.SPACE,
    }


def test_selected_resource_is_one_of_available_candidates() -> None:
    network = build_network()
    user = MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
    )
    association = evaluate_unified_network(
        network=network,
        users=[user],
        demands_bps={"user-01": 10e6},
        timestamp_s=0,
    ).associations[0]
    assert association.selected_resource_id is not None
    selected = next(
        candidate
        for candidate in association.candidates
        if candidate.resource_id == association.selected_resource_id
    )
    assert selected.available
    assert association.selected_domain is selected.domain


def test_unified_association_is_deterministic() -> None:
    network = build_network()
    users = [
        MobileUser(
            user_id="user-02",
            initial_position=GeoPoint(latitude_deg=17.39, longitude_deg=78.49, altitude_m=540),
        ),
        MobileUser(
            user_id="user-01",
            initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
        ),
    ]
    kwargs = {
        "network": network,
        "users": users,
        "demands_bps": {"user-01": 10e6, "user-02": 10e6},
        "timestamp_s": 0,
    }
    first = evaluate_unified_network(**kwargs)
    second = evaluate_unified_network(**kwargs)
    assert first.model_dump() == second.model_dump()


def test_duplicate_resource_ids_across_domains_are_rejected() -> None:
    ground = GroundNetwork(
        name="ground",
        cells=[
            GroundCell(
                cell_id="same",
                position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=43,
                tx_gain_dbi=14,
                noise_figure_db=5,
                required_sinr_db=8,
                maximum_service_distance_m=6_000,
                propagation_losses=LOSSES,
            )
        ],
    )
    duplicated_air = build_network().air.model_copy(
        update={
            "platforms": [
                build_network().air.platforms[0].model_copy(
                    update={"platform_id": "same"}
                )
            ]
        }
    )
    base = build_network()
    with pytest.raises(ValidationError):
        UnifiedNetwork(
            name="invalid",
            ground=ground,
            air=duplicated_air,
            space=base.space,
            satellite_radio=base.satellite_radio,
        )
