from __future__ import annotations

import math
from itertools import pairwise

import pytest

from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.space.constellation import (
    constellation_visibility,
    predict_passes,
    propagate_constellation,
)
from sag_network.space.selection import SatelliteCandidate, select_best_satellite


def _orbit(mean_anomaly_deg: float, raan_deg: float = 0.0) -> OrbitalElements:
    return OrbitalElements(
        semi_major_axis_m=6_378_137.0 + 550_000.0,
        eccentricity=0.0,
        inclination_deg=53.0,
        raan_deg=raan_deg,
        argument_of_perigee_deg=0.0,
        mean_anomaly_deg=mean_anomaly_deg,
    )


def test_constellation_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        Constellation(
            name="test",
            satellites=[
                SatelliteDefinition(satellite_id="sat-1", orbital_elements=_orbit(0.0)),
                SatelliteDefinition(satellite_id="sat-1", orbital_elements=_orbit(20.0)),
            ],
        )


def test_propagate_constellation_returns_all_active_members() -> None:
    constellation = Constellation(
        name="test",
        satellites=[
            SatelliteDefinition(satellite_id="sat-1", orbital_elements=_orbit(0.0)),
            SatelliteDefinition(satellite_id="sat-2", orbital_elements=_orbit(30.0)),
            SatelliteDefinition(
                satellite_id="sat-3", orbital_elements=_orbit(60.0), active=False
            ),
        ],
    )
    states = propagate_constellation(constellation, 60.0)
    assert set(states) == {"sat-1", "sat-2"}
    for state in states.values():
        radius = math.sqrt(
            state.position_ecef.x_m**2
            + state.position_ecef.y_m**2
            + state.position_ecef.z_m**2
        )
        assert radius > 6_378_137.0


def test_constellation_visibility_is_deterministic() -> None:
    constellation = Constellation(
        name="test",
        satellites=[
            SatelliteDefinition(satellite_id="sat-1", orbital_elements=_orbit(0.0)),
            SatelliteDefinition(satellite_id="sat-2", orbital_elements=_orbit(180.0)),
        ],
    )
    ground = GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0)
    first = constellation_visibility(constellation, "gs-001", ground, 0.0)
    second = constellation_visibility(constellation, "gs-001", ground, 0.0)
    assert first == second


def test_pass_prediction_returns_ordered_positive_duration_passes() -> None:
    satellite = SatelliteDefinition(satellite_id="sat-1", orbital_elements=_orbit(0.0))
    ground = GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0)
    passes = predict_passes(
        satellite=satellite,
        ground_position=ground,
        start_time_s=0.0,
        end_time_s=6_000.0,
        sample_step_s=30.0,
    )
    assert passes
    assert all(pass_window.aos_s < pass_window.los_s for pass_window in passes)
    assert all(pass_window.duration_s > 0 for pass_window in passes)
    assert all(
        pass_window.max_elevation_deg >= satellite.minimum_elevation_deg
        for pass_window in passes
    )
    assert all(
        first.los_s <= second.aos_s for first, second in pairwise(passes)
    )


def test_selector_ignores_unavailable_satellites() -> None:
    candidates = [
        SatelliteCandidate(
            satellite_id="bad",
            available=False,
            link_margin_db=100.0,
            elevation_deg=80.0,
            shannon_capacity_bps=1e9,
            propagation_delay_ms=2.0,
            doppler_shift_hz=100.0,
        ),
        SatelliteCandidate(
            satellite_id="good",
            available=True,
            link_margin_db=5.0,
            elevation_deg=30.0,
            shannon_capacity_bps=5e7,
            propagation_delay_ms=8.0,
            doppler_shift_hz=1000.0,
        ),
    ]
    selected = select_best_satellite(candidates)
    assert selected is not None
    assert selected.satellite_id == "good"


def test_selector_prefers_link_margin_before_secondary_metrics() -> None:
    candidates = [
        SatelliteCandidate(
            satellite_id="sat-low-margin",
            available=True,
            link_margin_db=6.0,
            elevation_deg=70.0,
            shannon_capacity_bps=1e9,
            propagation_delay_ms=1.0,
            doppler_shift_hz=100.0,
            predicted_loss_time_s=1_000.0,
        ),
        SatelliteCandidate(
            satellite_id="sat-high-margin",
            available=True,
            link_margin_db=9.0,
            elevation_deg=30.0,
            shannon_capacity_bps=1e6,
            propagation_delay_ms=20.0,
            doppler_shift_hz=5_000.0,
            predicted_loss_time_s=10.0,
        ),
    ]
    selected = select_best_satellite(candidates)
    assert selected is not None
    assert selected.satellite_id == "sat-high-margin"
