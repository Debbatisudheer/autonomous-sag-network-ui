from __future__ import annotations

from sag_network.domain.air import AirNetwork, AirPlatform, AirPlatformType
from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.models import GeoPoint
from sag_network.domain.unified import SatelliteRadioProfile, UnifiedNetwork
from sag_network.domain.unified_handover import UnifiedHandoverEventType
from sag_network.unified.cross_domain import run_cross_domain_mobility
from sag_network.unified.handover import UnifiedHandoverController


LOSSES = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=1.0,
    polarization_db=1.0,
    implementation_db=2.0,
)


def build_network() -> UnifiedNetwork:
    return UnifiedNetwork(
        name="helper-test",
        ground=GroundNetwork(
            name="ground",
            cells=[
                GroundCell(
                    cell_id="ground-1",
                    position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
                    carrier_frequency_hz=3.5e9,
                    bandwidth_hz=20e6,
                    tx_power_dbm=43.0,
                    tx_gain_dbi=14.0,
                    noise_figure_db=5.0,
                    required_sinr_db=8.0,
                    maximum_service_distance_m=6_000,
                    propagation_losses=LOSSES,
                )
            ],
        ),
        air=AirNetwork(
            name="air",
            platforms=[
                AirPlatform(
                    platform_id="air-1",
                    platform_type=AirPlatformType.HAPS,
                    initial_position=GeoPoint(
                        latitude_deg=18.0, longitude_deg=79.0, altitude_m=20_000
                    ),
                    carrier_frequency_hz=3.5e9,
                    bandwidth_hz=20e6,
                    tx_power_dbm=10.0,
                    tx_gain_dbi=0.0,
                    rx_gain_dbi=0.0,
                    noise_figure_db=5.0,
                    required_sinr_db=100.0,
                    maximum_service_distance_m=1.0,
                    propagation_losses=LOSSES,
                    initial_energy_wh=100.0,
                    reserve_energy_wh=20.0,
                    hotel_power_w=1.0,
                    propulsion_power_w=0.0,
                )
            ],
        ),
        space=Constellation(
            name="space",
            satellites=[
                SatelliteDefinition(
                    satellite_id="space-1",
                    orbital_elements={
                        "semi_major_axis_m": 6_928_137.0,
                        "eccentricity": 0.0,
                        "inclination_deg": 53.0,
                        "raan_deg": 75.0,
                        "argument_of_perigee_deg": 0.0,
                        "mean_anomaly_deg": 0.0,
                    },
                    minimum_elevation_deg=90.0,
                )
            ],
        ),
        satellite_radio=SatelliteRadioProfile(
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=44.0,
            tx_gain_dbi=25.0,
            rx_gain_dbi=20.0,
            noise_figure_db=5.0,
            propagation_losses=LOSSES,
            required_sinr_db=8.0,
        ),
    )


def test_cross_domain_helper_returns_one_event_per_timestamp() -> None:
    network = build_network()
    user = MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
    )
    events = run_cross_domain_mobility(
        network=network,
        users=[user],
        demands_bps={"user-01": 10e6},
        timestamps_s=(0.0, 10.0, 20.0),
        controllers={"user-01": UnifiedHandoverController()},
    )
    assert len(events["user-01"]) == 3
    assert events["user-01"][0].event_type is UnifiedHandoverEventType.ATTACH
    assert all(event.new_resource_id == "ground-1" for event in events["user-01"])


def test_cross_domain_helper_rejects_non_monotonic_time() -> None:
    network = build_network()
    user = MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=17.385, longitude_deg=78.487, altitude_m=540),
    )
    import pytest

    with pytest.raises(ValueError, match="non-decreasing"):
        run_cross_domain_mobility(
            network=network,
            users=[user],
            demands_bps={"user-01": 10e6},
            timestamps_s=(10.0, 5.0),
        )
