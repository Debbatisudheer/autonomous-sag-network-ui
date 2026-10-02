from __future__ import annotations

import json

from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.link import PropagationLosses
from sag_network.domain.models import GeoPoint
from sag_network.space.constellation import predict_passes
from sag_network.space.link import satellite_link_state
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.selection import SatelliteCandidate, select_best_satellite

ground = GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=540.0)
base_altitude_m = 550_000.0
base_radius_m = 6_378_137.0 + base_altitude_m

constellation = Constellation(
    name="analytical-leo-demo",
    satellites=[
        SatelliteDefinition(
            satellite_id="leo-01",
            orbital_elements={
                "semi_major_axis_m": base_radius_m,
                "eccentricity": 0.0,
                "inclination_deg": 53.0,
                "raan_deg": 75.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 0.0,
            },
        ),
        SatelliteDefinition(
            satellite_id="leo-02",
            orbital_elements={
                "semi_major_axis_m": base_radius_m,
                "eccentricity": 0.0,
                "inclination_deg": 53.0,
                "raan_deg": 285.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 180.0,
            },
        ),
        SatelliteDefinition(
            satellite_id="leo-03",
            orbital_elements={
                "semi_major_axis_m": base_radius_m,
                "eccentricity": 0.0,
                "inclination_deg": 53.0,
                "raan_deg": 90.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 180.0,
            },
        ),
        SatelliteDefinition(
            satellite_id="leo-04",
            orbital_elements={
                "semi_major_axis_m": base_radius_m,
                "eccentricity": 0.0,
                "inclination_deg": 53.0,
                "raan_deg": 270.0,
                "argument_of_perigee_deg": 0.0,
                "mean_anomaly_deg": 0.0,
            },
        ),
    ],
)

losses = PropagationLosses(
    atmospheric_db=1.0,
    rain_db=0.5,
    polarization_db=0.5,
    implementation_db=1.0,
)


def candidate_at(timestamp_s: float, satellite: SatelliteDefinition) -> SatelliteCandidate:
    state = propagate_satellite_state(satellite.orbital_elements, timestamp_s)
    link = satellite_link_state(
        timestamp_s=timestamp_s,
        ground_station_id="hyd-001",
        ground_position=ground,
        satellite_position_ecef=state.position_ecef,
        satellite_velocity_ecef=state.velocity_ecef,
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=44.0,
        tx_gain_dbi=25.0,
        rx_gain_dbi=20.0,
        noise_figure_db=5.0,
        propagation_losses=losses,
        required_sinr_db=8.0,
        minimum_elevation_deg=satellite.minimum_elevation_deg,
    )
    future_passes = predict_passes(
        satellite=satellite,
        ground_position=ground,
        start_time_s=timestamp_s,
        end_time_s=timestamp_s + 7_200.0,
        sample_step_s=30.0,
    )
    future_loss = next(
        (pass_window.los_s for pass_window in future_passes if pass_window.aos_s <= timestamp_s),
        None,
    )
    if future_loss is None and link["visible"]:
        future_loss = min(
            (pass_window.los_s for pass_window in future_passes if pass_window.los_s > timestamp_s),
            default=None,
        )

    return SatelliteCandidate(
        satellite_id=satellite.satellite_id,
        available=bool(link["available"]),
        link_margin_db=float(link["link_margin_db"]),
        elevation_deg=float(link["elevation_deg"]),
        shannon_capacity_bps=float(link["shannon_capacity_bps"]),
        propagation_delay_ms=float(link["propagation_delay_ms"]),
        doppler_shift_hz=float(link["doppler_shift_hz"]),
        predicted_loss_time_s=future_loss,
    )


# Deliberately deterministic snapshot: no random state and no synthetic measurements.
timestamp_s = 180.0
candidates = [candidate_at(timestamp_s, satellite) for satellite in constellation.satellites]
selected = select_best_satellite(candidates)

print(json.dumps({"timestamp_s": timestamp_s, "candidates": [candidate.__dict__ for candidate in candidates]}, indent=2))
print(
    json.dumps(
        {
            "selected_satellite_id": None if selected is None else selected.satellite_id,
            "selection_policy": "safety_first_baseline",
        },
        indent=2,
    )
)

for satellite in constellation.satellites:
    passes = predict_passes(
        satellite=satellite,
        ground_position=ground,
        start_time_s=0.0,
        end_time_s=7_200.0,
        sample_step_s=30.0,
    )
    print(
        json.dumps(
            {
                "satellite_id": satellite.satellite_id,
                "passes": [pass_window.model_dump() for pass_window in passes[:3]],
            },
            indent=2,
        )
    )
