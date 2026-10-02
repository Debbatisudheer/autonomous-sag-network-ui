from __future__ import annotations

from datetime import datetime, timedelta, UTC
from pathlib import Path

import pytest

from sag_network.domain.air import AirPlatformType
from sag_network.domain.link import PropagationLosses
from sag_network.trajectory.air import build_air_network_at
from sag_network.trajectory.kinematics import state_at
from sag_network.trajectory.loader import (
    load_csv_trajectory,
    load_geojson_trajectory,
    load_orion_trajectory,
)
from sag_network.trajectory.manifest import build_manifest
from sag_network.trajectory.models import (
    AerialRadioProfile,
    AerialTrajectory,
    AerialTrajectoryConfig,
    AerialTrajectoryDataset,
    AerialTrajectoryPoint,
    AerialTrajectorySourceType,
)


ROOT = Path(__file__).resolve().parents[1]
ORION_SAMPLE = ROOT / "data" / "air" / "orion-allowed-traj1-sample.jsonl"


def _radio_profile() -> AerialRadioProfile:
    return AerialRadioProfile(
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30.0,
        noise_figure_db=5.0,
        maximum_service_distance_m=25_000.0,
        initial_energy_wh=5_000.0,
        reserve_energy_wh=500.0,
        hotel_power_w=120.0,
        propulsion_power_w=400.0,
    )


def test_real_orion_schema_loads() -> None:
    dataset = load_orion_trajectory(
        ORION_SAMPLE,
        dataset_id="orion-sample",
        source_name="ORION",
        attribution="ORION real drone trajectory dataset",
        platform_id="uav-01",
        source_uri="https://github.com/ssciancalepore/orion-data/blob/main/allowed_traj_1.txt",
    )
    trajectory = dataset.trajectories[0]
    assert trajectory.source_type is AerialTrajectorySourceType.ORION_DRONE
    assert len(trajectory.points) == 12
    assert trajectory.points[0].timestamp_utc.year == 2022
    assert trajectory.points[0].position.altitude_m == pytest.approx(44.7, abs=0.2)
    assert len(dataset.fingerprint) == 64


def test_manifest_counts_points() -> None:
    dataset = load_orion_trajectory(
        ORION_SAMPLE,
        dataset_id="orion-sample",
        source_name="ORION",
        attribution="ORION",
        platform_id="uav-01",
    )
    manifest = build_manifest(dataset)
    assert manifest.trajectory_count == 1
    assert manifest.total_point_count == 12
    assert manifest.fingerprint == dataset.fingerprint


def test_state_at_exact_point_and_interpolated_point() -> None:
    dataset = load_orion_trajectory(
        ORION_SAMPLE,
        dataset_id="orion-sample",
        source_name="ORION",
        attribution="ORION",
        platform_id="uav-01",
    )
    trajectory = dataset.trajectories[0]
    exact = state_at(trajectory, trajectory.points[2].timestamp_utc)
    assert exact.source_interpolated is False
    middle = trajectory.points[1].timestamp_utc + (
        trajectory.points[2].timestamp_utc - trajectory.points[1].timestamp_utc
    ) / 2
    interpolated = state_at(trajectory, middle)
    assert interpolated.source_interpolated is True
    assert interpolated.position.latitude_deg == pytest.approx(
        (trajectory.points[1].position.latitude_deg + trajectory.points[2].position.latitude_deg)
        / 2
    )


def test_state_at_rejects_large_interpolation_gap() -> None:
    dataset = load_orion_trajectory(
        ORION_SAMPLE,
        dataset_id="orion-sample",
        source_name="ORION",
        attribution="ORION",
        platform_id="uav-01",
    )
    trajectory = dataset.trajectories[0]
    between = trajectory.points[0].timestamp_utc + timedelta(seconds=1)
    with pytest.raises(ValueError, match="interpolation gap"):
        state_at(
            trajectory,
            between,
            config=AerialTrajectoryConfig(maximum_interpolation_gap_s=0.5),
        )


def test_state_at_rejects_outside_coverage() -> None:
    dataset = load_orion_trajectory(
        ORION_SAMPLE,
        dataset_id="orion-sample",
        source_name="ORION",
        attribution="ORION",
        platform_id="uav-01",
    )
    with pytest.raises(ValueError, match="outside the trajectory coverage"):
        state_at(
            dataset.trajectories[0],
            dataset.trajectories[0].points[0].timestamp_utc - timedelta(seconds=1),
        )


def test_haps_contract_is_supported() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    points = [
        AerialTrajectoryPoint(
            timestamp_utc=start + timedelta(seconds=i),
            position={
                "latitude_deg": 17.385 + i * 0.0001,
                "longitude_deg": 78.487,
                "altitude_m": 20_000.0,
            },
        )
        for i in range(2)
    ]
    trajectory = AerialTrajectory(
        trajectory_id="haps-external-01",
        platform_id="haps-01",
        platform_type=AirPlatformType.HAPS,
        source_type=AerialTrajectorySourceType.HAPS_EXTERNAL,
        source_uri="https://example.invalid/haps.csv",
        attribution="External HAPS source",
        points=points,
        fingerprint="0" * 64,
    )
    dataset = AerialTrajectoryDataset(
        dataset_id="haps",
        source_name="external-haps",
        source_uri=trajectory.source_uri,
        attribution=trajectory.attribution,
        trajectories=[trajectory],
        fingerprint="1" * 64,
    )
    assert dataset.trajectories[0].platform_type is AirPlatformType.HAPS


def test_csv_loader(tmp_path: Path) -> None:
    csv_payload = (
        "timestamp,latitude_deg,longitude_deg,altitude_m\n"
        "0,17.0,78.0,100\n"
        "1,17.0001,78.0001,101\n"
    )
    def _write_csv(path: Path) -> None:
        path.write_text(csv_payload, encoding="utf-8")

    filename_path = tmp_path / "trajectory.csv"
    _write_csv(filename_path)
    dataset = load_csv_trajectory(
        filename_path,
        dataset_id="csv",
        source_name="csv",
        attribution="test",
        platform_id="uav-csv",
    )
    assert len(dataset.trajectories[0].points) == 2


def test_geojson_loader() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [78.0, 17.0, 100.0]},
                "properties": {"timestamp_utc": "2026-01-01T00:00:00Z"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [78.0001, 17.0001, 101.0]},
                "properties": {"timestamp_utc": "2026-01-01T00:00:01Z"},
            },
        ],
    }
    dataset = load_geojson_trajectory(
        payload,
        dataset_id="geojson",
        source_name="geojson",
        attribution="test",
        platform_id="uav-geo",
    )
    assert dataset.trajectories[0].platform_id == "uav-geo"
    assert dataset.trajectories[0].points[1].position.altitude_m == 101.0


def test_external_trajectory_projects_into_existing_air_network() -> None:
    dataset = load_orion_trajectory(
        ORION_SAMPLE,
        dataset_id="orion-sample",
        source_name="ORION",
        attribution="ORION",
        platform_id="uav-01",
    )
    timestamp = dataset.trajectories[0].points[4].timestamp_utc
    network = build_air_network_at(
        dataset,
        timestamp_utc=timestamp,
        radio_profile=_radio_profile(),
        propagation_losses=PropagationLosses(
            atmospheric_db=0.5,
            rain_db=0.5,
            polarization_db=0.2,
            implementation_db=0.8,
        ),
        simulation_epoch_utc=dataset.trajectories[0].points[0].timestamp_utc,
    )
    assert len(network.platforms) == 1
    assert network.platforms[0].platform_id == "uav-01"
    assert network.platforms[0].platform_type is AirPlatformType.UAV
