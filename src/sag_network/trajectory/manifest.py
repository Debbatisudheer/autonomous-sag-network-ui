from __future__ import annotations

from sag_network.trajectory.models import AerialTrajectoryDataset, AerialTrajectoryManifest


def build_manifest(dataset: AerialTrajectoryDataset) -> AerialTrajectoryManifest:
    """Build compact reproducibility metadata for an imported aerial dataset."""
    return AerialTrajectoryManifest(
        dataset_id=dataset.dataset_id,
        source_name=dataset.source_name,
        source_uri=dataset.source_uri,
        attribution=dataset.attribution,
        trajectory_count=len(dataset.trajectories),
        total_point_count=sum(len(item.points) for item in dataset.trajectories),
        fingerprint=dataset.fingerprint,
    )
