from __future__ import annotations

import json
from pathlib import Path

from sag_network.domain.link import PropagationLosses
from sag_network.trajectory.air import build_air_network_at
from sag_network.trajectory.kinematics import state_at
from sag_network.trajectory.loader import load_orion_trajectory
from sag_network.trajectory.manifest import build_manifest
from sag_network.trajectory.models import AerialRadioProfile

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "air" / "orion-allowed-traj1-sample.jsonl"
SOURCE_URI = "https://github.com/ssciancalepore/orion-data/blob/main/allowed_traj_1.txt"


def main() -> None:
    dataset = load_orion_trajectory(
        DATASET,
        dataset_id="orion-allowed-traj1-sample",
        source_name="ORION real drone trajectory sample",
        attribution="ORION drone trajectory dataset; see data/air/ORION-LICENSE-NOTICE.txt",
        platform_id="uav-orion-01",
        source_uri=SOURCE_URI,
    )
    trajectory = dataset.trajectories[0]
    first_timestamp = trajectory.points[0].timestamp_utc
    last_timestamp = trajectory.points[-1].timestamp_utc
    middle_timestamp = first_timestamp + (last_timestamp - first_timestamp) / 2
    middle_state = state_at(trajectory, middle_timestamp)
    network = build_air_network_at(
        dataset,
        timestamp_utc=middle_timestamp,
        radio_profile=AerialRadioProfile(
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=30.0,
            noise_figure_db=5.0,
            maximum_service_distance_m=25_000.0,
            initial_energy_wh=5_000.0,
            reserve_energy_wh=500.0,
            hotel_power_w=120.0,
            propulsion_power_w=400.0,
        ),
        propagation_losses=PropagationLosses(
            atmospheric_db=0.5,
            rain_db=0.5,
            polarization_db=0.2,
            implementation_db=0.8,
        ),
        simulation_epoch_utc=first_timestamp,
    )
    manifest = build_manifest(dataset)
    print(
        json.dumps(
            {
                "status": "pass",
                "dataset_id": dataset.dataset_id,
                "source_name": dataset.source_name,
                "source_uri": dataset.source_uri,
                "platform_id": trajectory.platform_id,
                "platform_type": trajectory.platform_type.value,
                "point_count": len(trajectory.points),
                "start_utc": first_timestamp.isoformat(),
                "end_utc": last_timestamp.isoformat(),
                "middle_state": {
                    "timestamp_utc": middle_state.timestamp_utc.isoformat(),
                    "latitude_deg": middle_state.position.latitude_deg,
                    "longitude_deg": middle_state.position.longitude_deg,
                    "altitude_m": middle_state.position.altitude_m,
                    "velocity_north_mps": middle_state.velocity_north_mps,
                    "velocity_east_mps": middle_state.velocity_east_mps,
                    "velocity_up_mps": middle_state.velocity_up_mps,
                    "speed_mps": middle_state.speed_mps,
                    "course_deg": middle_state.course_deg,
                    "interpolated": middle_state.source_interpolated,
                },
                "air_network_platforms": [platform.platform_id for platform in network.platforms],
                "manifest": manifest.model_dump(mode="json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
