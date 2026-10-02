from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from sag_network.domain.models import GeoPoint
from sag_network.geospatial.models import (
    GroundGeospatialSourceType,
    GroundSiteDataset,
    GroundSiteRecord,
)


def _as_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _load_payload(source: str | Path | dict[str, Any]) -> tuple[dict[str, Any], str]:
    if isinstance(source, dict):
        return source, "inline://geojson"
    path = Path(source)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("GeoJSON root must be an object")
    return cast(dict[str, Any], payload), path.as_uri()


def load_ground_sites_geojson(
    source: str | Path | dict[str, Any],
    *,
    dataset_id: str,
    source_name: str,
    attribution: str,
) -> GroundSiteDataset:
    """Load a GeoJSON FeatureCollection containing Point ground sites.

    The loader intentionally accepts only Point geometry so altitude semantics remain
    unambiguous for network-site placement. Non-point features are rejected explicitly.
    """
    payload, source_uri = _load_payload(source)
    if payload.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON must contain a FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("GeoJSON FeatureCollection contains no features")

    sites: list[GroundSiteRecord] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise TypeError(f"feature {index} must be an object")
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            raise ValueError(f"feature {index} must use Point geometry")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError(f"feature {index} requires [longitude, latitude]")
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
        altitude = float(coordinates[2]) if len(coordinates) >= 3 else 0.0
        properties = feature.get("properties") or {}
        if not isinstance(properties, dict):
            raise TypeError(f"feature {index} properties must be an object")
        raw_site_id = properties.get("site_id", feature.get("id", f"site-{index + 1}"))
        site_id = _as_str(raw_site_id, "site_id")
        name = _as_str(properties.get("name", site_id), "name")
        tags = {
            str(key): str(value)
            for key, value in properties.items()
            if key not in {"site_id", "name", "feature_type"}
        }
        sites.append(
            GroundSiteRecord(
                site_id=site_id,
                name=name,
                position=GeoPoint(
                    latitude_deg=latitude,
                    longitude_deg=longitude,
                    altitude_m=max(0.0, altitude),
                ),
                source_type=GroundGeospatialSourceType.GEOJSON,
                source_uri=source_uri,
                source_feature_id=str(feature.get("id")) if feature.get("id") is not None else None,
                feature_type=(
                    str(properties["feature_type"])
                    if "feature_type" in properties
                    else None
                ),
                tags=tags,
            )
        )

    return GroundSiteDataset(
        dataset_id=dataset_id,
        source_name=source_name,
        source_uri=source_uri,
        attribution=attribution,
        sites=sites,
        fingerprint=fingerprint_sites(sites),
    )


def fingerprint_sites(sites: list[GroundSiteRecord]) -> str:
    canonical = [
        {
            "site_id": site.site_id,
            "name": site.name,
            "latitude_deg": site.position.latitude_deg,
            "longitude_deg": site.position.longitude_deg,
            "altitude_m": site.position.altitude_m,
            "source_type": site.source_type.value,
            "source_feature_id": site.source_feature_id,
            "feature_type": site.feature_type,
            "tags": dict(sorted(site.tags.items())),
        }
        for site in sorted(sites, key=lambda item: item.site_id)
    ]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()
