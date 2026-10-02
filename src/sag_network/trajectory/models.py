from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sag_network.domain.air import AirPlatformType
from sag_network.domain.models import GeoPoint


class AerialTrajectorySourceType(StrEnum):
    ORION_DRONE = "orion_drone"
    JSONL = "jsonl"
    CSV = "csv"
    GEOJSON = "geojson"
    HAPS_EXTERNAL = "haps_external"
    MANUAL = "manual"


class AerialTrajectoryPoint(BaseModel):
    """One time-stamped WGS84 observation from an external aerial trajectory."""

    timestamp_utc: datetime
    position: GeoPoint


class AerialTrajectory(BaseModel):
    """Validated time-ordered trajectory for one UAV or HAPS platform."""

    trajectory_id: str = Field(min_length=1)
    platform_id: str = Field(min_length=1)
    platform_type: AirPlatformType
    source_type: AerialTrajectorySourceType
    source_uri: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    points: list[AerialTrajectoryPoint] = Field(min_length=2)
    fingerprint: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_points(self) -> AerialTrajectory:
        ordered = [point.timestamp_utc for point in self.points]
        if any(left >= right for left, right in pairwise(ordered)):
            raise ValueError("trajectory timestamps must be strictly increasing")
        return self


class AerialTrajectoryDataset(BaseModel):
    """Validated collection of external aerial trajectories."""

    dataset_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    trajectories: list[AerialTrajectory] = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> AerialTrajectoryDataset:
        ids = [item.platform_id for item in self.trajectories]
        if len(ids) != len(set(ids)):
            raise ValueError("platform_id values must be unique within an aerial dataset")
        return self


class AerialTrajectoryConfig(BaseModel):
    """Interpolation and data-quality limits for replaying an aerial trajectory."""

    maximum_interpolation_gap_s: float = Field(gt=0, default=30.0)
    allow_interpolation: bool = True
    require_timezone_aware: bool = True


class AerialTrajectoryState(BaseModel):
    """Interpolated trajectory state with geodetic and local kinematic quantities."""

    trajectory_id: str = Field(min_length=1)
    platform_id: str = Field(min_length=1)
    platform_type: AirPlatformType
    timestamp_utc: datetime
    position: GeoPoint
    velocity_north_mps: float
    velocity_east_mps: float
    velocity_up_mps: float
    speed_mps: float = Field(ge=0)
    course_deg: float = Field(ge=0, lt=360)
    source_interpolated: bool


class AerialRadioProfile(BaseModel):
    """Radio/energy configuration used when projecting external trajectories into AirNetwork."""

    carrier_frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    tx_power_dbm: float
    tx_gain_dbi: float = 0.0
    rx_gain_dbi: float = 0.0
    noise_figure_db: float = Field(ge=0)
    required_sinr_db: float = 0.0
    maximum_service_distance_m: float = Field(gt=0)
    scheduler_efficiency: float = Field(gt=0, le=1.0, default=0.75)
    initial_energy_wh: float = Field(gt=0)
    reserve_energy_wh: float = Field(ge=0, default=0.0)
    hotel_power_w: float = Field(gt=0)
    propulsion_power_w: float = Field(ge=0, default=0.0)

    @model_validator(mode="after")
    def validate_energy(self) -> AerialRadioProfile:
        if self.reserve_energy_wh >= self.initial_energy_wh:
            raise ValueError("reserve_energy_wh must be less than initial_energy_wh")
        return self


class AerialTrajectoryManifest(BaseModel):
    """Reproducibility metadata for an externally supplied aerial dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    trajectory_count: int = Field(gt=0)
    total_point_count: int = Field(gt=0)
    fingerprint: str = Field(min_length=64, max_length=64)
