from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sag_network.domain.air import AirPlatformType
from sag_network.domain.models import GeoPoint
from sag_network.trajectory.models import (
    AerialTrajectory,
    AerialTrajectoryDataset,
    AerialTrajectoryPoint,
    AerialTrajectorySourceType,
)


def _as_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _parse_timestamp(value: object, *, unit: str) -> datetime:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if unit == "milliseconds":
            numeric /= 1000.0
        elif unit != "seconds":
            raise ValueError("timestamp_unit must be seconds or milliseconds")
        return datetime.fromtimestamp(numeric, tz=UTC)
    if isinstance(value, str):
        text = value.strip()
        if text.replace(".", "", 1).isdigit() and unit in {"seconds", "milliseconds"}:
            return _parse_timestamp(float(text), unit=unit)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        timestamp = datetime.fromisoformat(text)
        if timestamp.tzinfo is None:
            raise ValueError("trajectory timestamp must be timezone-aware")
        return timestamp.astimezone(UTC)
    raise TypeError("trajectory timestamp must be numeric or ISO-8601 text")


def _build_dataset(
    *,
    dataset_id: str,
    source_name: str,
    source_uri: str,
    attribution: str,
    source_type: AerialTrajectorySourceType,
    points_by_platform: dict[tuple[str, str], list[AerialTrajectoryPoint]],
    platform_types: dict[str, AirPlatformType],
) -> AerialTrajectoryDataset:
    trajectories: list[AerialTrajectory] = []
    for (trajectory_id, platform_id), points in sorted(points_by_platform.items()):
        platform_type = platform_types[platform_id]
        canonical = [
            {
                "timestamp_utc": point.timestamp_utc.isoformat(),
                "latitude_deg": point.position.latitude_deg,
                "longitude_deg": point.position.longitude_deg,
                "altitude_m": point.position.altitude_m,
            }
            for point in points
        ]
        fingerprint = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        trajectories.append(
            AerialTrajectory(
                trajectory_id=trajectory_id,
                platform_id=platform_id,
                platform_type=platform_type,
                source_type=source_type,
                source_uri=source_uri,
                attribution=attribution,
                points=points,
                fingerprint=fingerprint,
            )
        )

    dataset_canonical = [
        {
            "platform_id": item.platform_id,
            "trajectory_id": item.trajectory_id,
            "fingerprint": item.fingerprint,
        }
        for item in trajectories
    ]
    dataset_fingerprint = hashlib.sha256(
        json.dumps(dataset_canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return AerialTrajectoryDataset(
        dataset_id=dataset_id,
        source_name=source_name,
        source_uri=source_uri,
        attribution=attribution,
        trajectories=trajectories,
        fingerprint=dataset_fingerprint,
    )


def load_jsonl_trajectory(
    source: str | Path,
    *,
    dataset_id: str,
    source_name: str,
    attribution: str,
    platform_id: str,
    platform_type: AirPlatformType = AirPlatformType.UAV,
    timestamp_field: str = "timestamp",
    timestamp_unit: str = "milliseconds",
    latitude_field: str = "latitude",
    longitude_field: str = "longitude",
    altitude_field: str = "altitude",
    record_type_field: str | None = "type",
    required_record_type: str | None = "location",
    source_uri: str | None = None,
    trajectory_id: str | None = None,
    source_type: AerialTrajectorySourceType = AerialTrajectorySourceType.JSONL,
) -> AerialTrajectoryDataset:
    """Load one external JSONL trajectory into the common aerial-data contract."""
    path = Path(source)
    points: list[AerialTrajectoryPoint] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise TypeError(f"line {line_number} must contain a JSON object")
        if (
            required_record_type is not None
            and record_type_field is not None
            and payload.get(record_type_field) != required_record_type
        ):
            continue
        timestamp = _parse_timestamp(payload.get(timestamp_field), unit=timestamp_unit)
        latitude = float(payload[latitude_field])
        longitude = float(payload[longitude_field])
        altitude = float(payload.get(altitude_field, 0.0))
        points.append(
            AerialTrajectoryPoint(
                timestamp_utc=timestamp,
                position=GeoPoint(
                    latitude_deg=latitude,
                    longitude_deg=longitude,
                    altitude_m=max(0.0, altitude),
                ),
            )
        )
    if len(points) < 2:
        raise ValueError("trajectory source must contain at least two location observations")
    trajectory_id_value = trajectory_id or f"{platform_id}-trajectory"
    return _build_dataset(
        dataset_id=dataset_id,
        source_name=source_name,
        source_uri=source_uri or path.as_uri(),
        attribution=attribution,
        source_type=source_type,
        points_by_platform={(trajectory_id_value, platform_id): points},
        platform_types={platform_id: platform_type},
    )


def load_orion_trajectory(
    source: str | Path,
    *,
    dataset_id: str,
    source_name: str,
    attribution: str,
    platform_id: str,
    source_uri: str | None = None,
    trajectory_id: str | None = None,
) -> AerialTrajectoryDataset:
    """Load an ORION real-drone JSONL trajectory using its published field schema."""
    return load_jsonl_trajectory(
        source,
        dataset_id=dataset_id,
        source_name=source_name,
        attribution=attribution,
        platform_id=platform_id,
        platform_type=AirPlatformType.UAV,
        timestamp_field="timestamp",
        timestamp_unit="milliseconds",
        latitude_field="latitude",
        longitude_field="longitude",
        altitude_field="altitude",
        record_type_field="type",
        required_record_type="location",
        source_uri=source_uri,
        trajectory_id=trajectory_id,
        source_type=AerialTrajectorySourceType.ORION_DRONE,
    )


def _row_value(row: dict[str, str], field: str, line_number: int) -> str:
    if field not in row:
        raise ValueError(f"CSV trajectory is missing required field {field!r} at row {line_number}")
    return _as_non_empty_string(row[field], field)


def load_csv_trajectory(
    source: str | Path,
    *,
    dataset_id: str,
    source_name: str,
    attribution: str,
    platform_id: str,
    platform_type: AirPlatformType = AirPlatformType.UAV,
    timestamp_field: str = "timestamp",
    timestamp_unit: str = "seconds",
    latitude_field: str = "latitude_deg",
    longitude_field: str = "longitude_deg",
    altitude_field: str = "altitude_m",
    source_uri: str | None = None,
    trajectory_id: str | None = None,
) -> AerialTrajectoryDataset:
    """Load a generic timestamped CSV trajectory into the common external-data contract."""
    path = Path(source)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        points: list[AerialTrajectoryPoint] = []
        for line_number, row in enumerate(reader, start=2):
            timestamp = _parse_timestamp(
                _row_value(row, timestamp_field, line_number), unit=timestamp_unit
            )
            points.append(
                AerialTrajectoryPoint(
                    timestamp_utc=timestamp,
                    position=GeoPoint(
                        latitude_deg=float(_row_value(row, latitude_field, line_number)),
                        longitude_deg=float(_row_value(row, longitude_field, line_number)),
                        altitude_m=max(0.0, float(_row_value(row, altitude_field, line_number))),
                    ),
                )
            )
    if len(points) < 2:
        raise ValueError("CSV trajectory must contain at least two observations")
    trajectory_id_value = trajectory_id or f"{platform_id}-trajectory"
    return _build_dataset(
        dataset_id=dataset_id,
        source_name=source_name,
        source_uri=source_uri or path.as_uri(),
        attribution=attribution,
        source_type=AerialTrajectorySourceType.CSV,
        points_by_platform={(trajectory_id_value, platform_id): points},
        platform_types={platform_id: platform_type},
    )


def load_geojson_trajectory(
    source: str | Path | dict[str, Any],
    *,
    dataset_id: str,
    source_name: str,
    attribution: str,
    platform_id: str,
    platform_type: AirPlatformType = AirPlatformType.UAV,
    source_uri: str = "inline://trajectory-geojson",
    timestamp_property: str = "timestamp_utc",
    altitude_default_m: float = 0.0,
    trajectory_id: str | None = None,
) -> AerialTrajectoryDataset:
    """Load a GeoJSON FeatureCollection containing timestamped Point observations."""
    if isinstance(source, dict):
        payload = source
    else:
        path = Path(source)
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_uri = path.as_uri()
    if payload.get("type") != "FeatureCollection":
        raise ValueError("trajectory GeoJSON must be a FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise TypeError("trajectory GeoJSON features must be an array")
    points: list[AerialTrajectoryPoint] = []
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            raise TypeError(f"trajectory feature {index} must be an object")
        geometry = feature.get("geometry")
        properties = feature.get("properties") or {}
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            raise ValueError(f"trajectory feature {index} must use Point geometry")
        if not isinstance(properties, dict):
            raise TypeError(f"trajectory feature {index} properties must be an object")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError(f"trajectory feature {index} requires [longitude, latitude]")
        timestamp = _parse_timestamp(properties[timestamp_property], unit="seconds")
        altitude = float(coordinates[2]) if len(coordinates) >= 3 else altitude_default_m
        points.append(
            AerialTrajectoryPoint(
                timestamp_utc=timestamp,
                position=GeoPoint(
                    latitude_deg=float(coordinates[1]),
                    longitude_deg=float(coordinates[0]),
                    altitude_m=max(0.0, altitude),
                ),
            )
        )
    if len(points) < 2:
        raise ValueError("trajectory GeoJSON must contain at least two observations")
    trajectory_id_value = trajectory_id or f"{platform_id}-trajectory"
    return _build_dataset(
        dataset_id=dataset_id,
        source_name=source_name,
        source_uri=source_uri,
        attribution=attribution,
        source_type=AerialTrajectorySourceType.GEOJSON,
        points_by_platform={(trajectory_id_value, platform_id): points},
        platform_types={platform_id: platform_type},
    )
