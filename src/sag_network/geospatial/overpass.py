from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sag_network.domain.models import GeoPoint
from sag_network.geospatial.geojson import fingerprint_sites
from sag_network.geospatial.models import (
    GroundGeospatialSourceType,
    GroundSiteDataset,
    GroundSiteRecord,
)


@dataclass(frozen=True)
class OverpassNode:
    """A point feature returned by the OpenStreetMap Overpass API."""

    osm_id: int
    latitude_deg: float
    longitude_deg: float
    tags: dict[str, str]


class OverpassClient:
    """Read-only Overpass client for bounded point-feature extraction."""

    def __init__(
        self,
        *,
        endpoint: str = "https://overpass-api.de/api/interpreter",
        timeout_s: float = 60.0,
        user_agent: str = "autonomous-sag-network/1.0",
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if not user_agent.strip():
            raise ValueError("user_agent must be non-empty")
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self.user_agent = user_agent

    def node_features(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
        tag_key: str,
        tag_value: str,
    ) -> list[OverpassNode]:
        if not -90 <= south <= 90 or not -90 <= north <= 90 or south >= north:
            raise ValueError("south/north must form a valid latitude range")
        if not -180 <= west <= 180 or not -180 <= east <= 180 or west >= east:
            raise ValueError("west/east must form a valid longitude range")
        if not tag_key.strip() or not tag_value.strip():
            raise ValueError("tag_key and tag_value must be non-empty")
        query = (
            f"[out:json][timeout:{int(self.timeout_s)}];"
            f'node["{tag_key}"="{tag_value}"]({south},{west},{north},{east});'
            "out;"
        )
        params = urlencode({"data": query})
        request = Request(
            f"{self.endpoint}?{params}",
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout_s) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
            raise TypeError("Overpass response must contain an elements array")
        nodes: list[OverpassNode] = []
        for element in payload["elements"]:
            if not isinstance(element, dict) or element.get("type") != "node":
                continue
            raw_tags = element.get("tags") or {}
            if not isinstance(raw_tags, dict):
                raise TypeError("Overpass node tags must be an object")
            nodes.append(
                OverpassNode(
                    osm_id=int(element["id"]),
                    latitude_deg=float(element["lat"]),
                    longitude_deg=float(element["lon"]),
                    tags={str(key): str(value) for key, value in raw_tags.items()},
                )
            )
        return nodes


def overpass_nodes_to_dataset(
    nodes: list[OverpassNode],
    *,
    dataset_id: str,
    source_uri: str,
    attribution: str,
    feature_type: str = "osm_node",
) -> GroundSiteDataset:
    """Convert Overpass point nodes into the canonical ground-site dataset model."""
    if not nodes:
        raise ValueError("nodes must contain at least one feature")
    sites = [
        GroundSiteRecord(
            site_id=f"osm-node-{node.osm_id}",
            name=node.tags.get("name", f"OSM node {node.osm_id}"),
            position=GeoPoint(
                latitude_deg=node.latitude_deg,
                longitude_deg=node.longitude_deg,
                altitude_m=0.0,
            ),
            source_type=GroundGeospatialSourceType.OSM,
            source_uri=source_uri,
            source_feature_id=f"node/{node.osm_id}",
            feature_type=feature_type,
            tags=node.tags,
        )
        for node in sorted(nodes, key=lambda item: item.osm_id)
    ]
    return GroundSiteDataset(
        dataset_id=dataset_id,
        source_name="OpenStreetMap Overpass",
        source_uri=source_uri,
        attribution=attribution,
        sites=sites,
        fingerprint=fingerprint_sites(sites),
    )
