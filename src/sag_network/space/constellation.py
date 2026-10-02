from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from sag_network.domain.constellation import Constellation, SatelliteDefinition, SatellitePass
from sag_network.domain.models import GeoPoint
from sag_network.domain.space import GroundSatelliteVisibility, SatelliteState
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.visibility import ground_to_satellite_visibility


@dataclass(frozen=True)
class VisibilitySample:
    """Internal visibility sample used to identify and refine pass boundaries."""

    timestamp_s: float
    visibility: GroundSatelliteVisibility


def propagate_constellation(
    constellation: Constellation,
    timestamp_s: float,
) -> dict[str, SatelliteState]:
    """Propagate every active constellation member at one simulation time."""
    if timestamp_s < 0:
        raise ValueError("timestamp_s must be non-negative")
    return {
        satellite.satellite_id: propagate_satellite_state(
            satellite.orbital_elements,
            timestamp_s,
        )
        for satellite in constellation.satellites
        if satellite.active
    }


def constellation_visibility(
    constellation: Constellation,
    ground_station_id: str,
    ground_position: GeoPoint,
    timestamp_s: float,
) -> dict[str, GroundSatelliteVisibility]:
    """Calculate ground visibility for all active satellites at one simulation time."""
    if not ground_station_id:
        raise ValueError("ground_station_id must not be empty")
    states = propagate_constellation(constellation, timestamp_s)
    by_id = {satellite.satellite_id: satellite for satellite in constellation.satellites}
    return {
        satellite_id: ground_to_satellite_visibility(
            timestamp_s=timestamp_s,
            ground_station_id=ground_station_id,
            ground_position=ground_position,
            satellite_position_ecef=state.position_ecef,
            minimum_elevation_deg=by_id[satellite_id].minimum_elevation_deg,
        )
        for satellite_id, state in states.items()
    }


def _visibility_sample(
    satellite: SatelliteDefinition,
    ground_position: GeoPoint,
    timestamp_s: float,
) -> VisibilitySample:
    state = propagate_satellite_state(satellite.orbital_elements, timestamp_s)
    visibility = ground_to_satellite_visibility(
        timestamp_s=timestamp_s,
        ground_station_id="ground",
        ground_position=ground_position,
        satellite_position_ecef=state.position_ecef,
        minimum_elevation_deg=satellite.minimum_elevation_deg,
    )
    return VisibilitySample(timestamp_s=timestamp_s, visibility=visibility)


def _refine_crossing(
    satellite: SatelliteDefinition,
    ground_position: GeoPoint,
    low: VisibilitySample,
    high: VisibilitySample,
    *,
    target_visible: bool,
    tolerance_s: float,
) -> float:
    """Bisect a visibility transition to sub-second timing."""
    low_visible = low.visibility.visible
    high_visible = high.visibility.visible
    if low_visible == high_visible:
        raise ValueError("refinement interval does not bracket a visibility transition")

    while high.timestamp_s - low.timestamp_s > tolerance_s:
        mid_time = (low.timestamp_s + high.timestamp_s) / 2.0
        mid = _visibility_sample(satellite, ground_position, mid_time)
        if mid.visibility.visible == target_visible:
            high = mid
        else:
            low = mid
    return (low.timestamp_s + high.timestamp_s) / 2.0


def predict_passes(
    *,
    satellite: SatelliteDefinition,
    ground_position: GeoPoint,
    start_time_s: float,
    end_time_s: float,
    sample_step_s: float = 30.0,
    boundary_tolerance_s: float = 0.25,
) -> list[SatellitePass]:
    """Predict visibility passes using physical propagation plus boundary refinement."""
    if start_time_s < 0 or end_time_s < start_time_s:
        raise ValueError("time range is invalid")
    if sample_step_s <= 0 or boundary_tolerance_s <= 0:
        raise ValueError("sampling and boundary tolerance must be positive")

    samples: list[VisibilitySample] = []
    timestamp_s = start_time_s
    while timestamp_s < end_time_s:
        samples.append(_visibility_sample(satellite, ground_position, timestamp_s))
        timestamp_s += sample_step_s
    samples.append(_visibility_sample(satellite, ground_position, end_time_s))

    passes: list[SatellitePass] = []
    in_pass = samples[0].visibility.visible if samples else False
    aos_s: float | None = start_time_s if in_pass else None
    max_sample = samples[0] if in_pass else None
    if in_pass:
        assert max_sample is not None

    for previous, current in pairwise(samples):
        if in_pass:
            assert max_sample is not None
            if current.visibility.elevation_deg > max_sample.visibility.elevation_deg:
                max_sample = current

        if not in_pass and not previous.visibility.visible and current.visibility.visible:
            aos_s = _refine_crossing(
                satellite,
                ground_position,
                previous,
                current,
                target_visible=True,
                tolerance_s=boundary_tolerance_s,
            )
            refined_aos = _visibility_sample(satellite, ground_position, aos_s)
            max_sample = refined_aos
            in_pass = True
        elif in_pass and previous.visibility.visible and not current.visibility.visible:
            los_s = _refine_crossing(
                satellite,
                ground_position,
                previous,
                current,
                target_visible=False,
                tolerance_s=boundary_tolerance_s,
            )
            assert aos_s is not None
            assert max_sample is not None
            passes.append(
                SatellitePass(
                    satellite_id=satellite.satellite_id,
                    aos_s=aos_s,
                    max_elevation_s=max_sample.timestamp_s,
                    max_elevation_deg=max_sample.visibility.elevation_deg,
                    los_s=los_s,
                )
            )
            aos_s = None
            max_sample = None
            in_pass = False

    if in_pass and aos_s is not None and max_sample is not None:
        passes.append(
            SatellitePass(
                satellite_id=satellite.satellite_id,
                aos_s=aos_s,
                max_elevation_s=max_sample.timestamp_s,
                max_elevation_deg=max_sample.visibility.elevation_deg,
                los_s=end_time_s,
            )
        )

    return passes
