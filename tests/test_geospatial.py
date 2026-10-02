from __future__ import annotations

import json
from pathlib import Path
from typing import Self
from unittest.mock import patch

import pytest

from sag_network.domain.link import PropagationLosses
from sag_network.geospatial.elevation import USGSElevationClient
from sag_network.geospatial.geojson import fingerprint_sites, load_ground_sites_geojson
from sag_network.geospatial.models import GroundGeospatialSourceType, GroundRadioProfile
from sag_network.geospatial.network import build_ground_network_from_sites
from sag_network.geospatial.osm import NominatimClient
from sag_network.geospatial.overpass import overpass_nodes_to_dataset, OverpassClient, OverpassNode

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "geospatial"
    / "ground-reference-india.geojson"
)


def test_geojson_fixture_loads_and_has_real_site_coordinates() -> None:
    dataset = load_ground_sites_geojson(
        FIXTURE,
        dataset_id="india-reference-cities-v1",
        source_name="Offline public city reference fixture",
        attribution="Reference coordinates retained for deterministic tests",
    )
    assert len(dataset.sites) == 4
    assert all(site.source_type is GroundGeospatialSourceType.GEOJSON for site in dataset.sites)
    assert dataset.fingerprint == fingerprint_sites(dataset.sites)
    assert all(-90 <= site.position.latitude_deg <= 90 for site in dataset.sites)


def test_geojson_rejects_non_point_geometry() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1, 2], [3, 4]]}}
        ],
    }
    with pytest.raises(ValueError, match="Point geometry"):
        load_ground_sites_geojson(
            payload,
            dataset_id="bad",
            source_name="test",
            attribution="test",
        )


def test_geojson_rejects_missing_features() -> None:
    with pytest.raises(ValueError, match="contains no features"):
        load_ground_sites_geojson(
            {"type": "FeatureCollection", "features": []},
            dataset_id="empty",
            source_name="test",
            attribution="test",
        )


def test_geojson_fingerprint_is_order_independent() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    forward = load_ground_sites_geojson(
        payload,
        dataset_id="one",
        source_name="test",
        attribution="test",
    )
    payload["features"] = list(reversed(payload["features"]))
    reverse = load_ground_sites_geojson(
        payload,
        dataset_id="two",
        source_name="test",
        attribution="test",
    )
    assert forward.fingerprint == reverse.fingerprint


def test_ground_network_builder_reuses_existing_ground_contract() -> None:
    dataset = load_ground_sites_geojson(
        FIXTURE,
        dataset_id="india-reference-cities-v1",
        source_name="test",
        attribution="test",
    )
    network = build_ground_network_from_sites(
        dataset,
        radio_profile=GroundRadioProfile(
            carrier_frequency_hz=3.5e9,
            bandwidth_hz=20e6,
            tx_power_dbm=43.0,
            noise_figure_db=5.0,
            maximum_service_distance_m=25_000.0,
        ),
        propagation_losses=PropagationLosses(
            atmospheric_db=0.5,
            rain_db=0.5,
            polarization_db=0.2,
            implementation_db=0.8,
        ),
        network_name="india-real-ground",
    )
    assert [cell.cell_id for cell in network.cells] == sorted(
        [site.site_id for site in dataset.sites]
    )
    site_by_id = {site.site_id: site for site in dataset.sites}
    assert network.cells[0].position == site_by_id[network.cells[0].cell_id].position


def test_nominatim_rejects_invalid_limits() -> None:
    client = NominatimClient(user_agent="test-agent", minimum_interval_s=0)
    with pytest.raises(ValueError, match="between 1 and 40"):
        client.search("Hyderabad", limit=0)


def test_nominatim_rejects_empty_queries() -> None:
    client = NominatimClient(user_agent="test-agent", minimum_interval_s=0)
    with pytest.raises(ValueError, match="non-empty"):
        client.search(" ")


def test_nominatim_maps_json_response() -> None:
    client = NominatimClient(user_agent="test-agent", minimum_interval_s=0)
    payload = json.dumps(
        [
            {
                "osm_type": "node",
                "osm_id": 123,
                "display_name": "Example",
                "lat": "17.3850",
                "lon": "78.4867",
                "class": "place",
                "type": "city",
            }
        ]
    ).encode()

    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return payload

    with patch("sag_network.geospatial.osm.urlopen", return_value=Response()):
        result = client.search("Hyderabad")
    assert result[0].osm_type == "node"
    assert result[0].osm_id == "123"
    assert result[0].latitude_deg == pytest.approx(17.3850)
    assert result[0].longitude_deg == pytest.approx(78.4867)


def test_nominatim_requires_user_agent() -> None:
    with pytest.raises(ValueError, match="user_agent"):
        NominatimClient(user_agent=" ")


def test_usgs_client_maps_point_response() -> None:
    client = USGSElevationClient(timeout_s=2.0)
    payload = json.dumps({"value": "123.45"}).encode()

    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return payload

    with patch("sag_network.geospatial.elevation.urlopen", return_value=Response()):
        result = client.elevation(latitude_deg=40.0, longitude_deg=-105.0)
    assert result.elevation_m == pytest.approx(123.45)
    assert "epqs" in result.source_uri


def test_usgs_client_rejects_bad_payload() -> None:
    client = USGSElevationClient(timeout_s=2.0)
    payload = json.dumps({"result": "not-an-elevation"}).encode()

    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return payload

    with patch("sag_network.geospatial.elevation.urlopen", return_value=Response()), pytest.raises(
        ValueError, match="elevation value"
    ):
        client.elevation(latitude_deg=40.0, longitude_deg=-105.0)


def test_usgs_client_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        USGSElevationClient(timeout_s=0)


def test_overpass_rejects_invalid_bbox() -> None:
    client = OverpassClient(timeout_s=2.0)
    with pytest.raises(ValueError, match="latitude range"):
        client.node_features(
            south=10.0, west=70.0, north=5.0, east=80.0, tag_key="man_made", tag_value="mast"
        )


def test_overpass_rejects_invalid_tag() -> None:
    client = OverpassClient(timeout_s=2.0)
    with pytest.raises(ValueError, match="tag_key"):
        client.node_features(
            south=10.0, west=70.0, north=20.0, east=80.0, tag_key=" ", tag_value="mast"
        )


def test_overpass_maps_node_response() -> None:
    client = OverpassClient(timeout_s=2.0)
    payload = json.dumps(
        {
            "elements": [
                {
                    "type": "node",
                    "id": 987,
                    "lat": 17.385,
                    "lon": 78.4867,
                    "tags": {"man_made": "mast", "tower:type": "communication"},
                }
            ]
        }
    ).encode()

    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return payload

    with patch("sag_network.geospatial.overpass.urlopen", return_value=Response()):
        result = client.node_features(
            south=17.0, west=78.0, north=18.0, east=79.0, tag_key="man_made", tag_value="mast"
        )
    assert result[0].osm_id == 987
    assert result[0].tags["tower:type"] == "communication"


def test_overpass_requires_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        OverpassClient(timeout_s=0)


def test_overpass_nodes_convert_to_ground_dataset() -> None:
    dataset = overpass_nodes_to_dataset(
        [
            OverpassNode(
                osm_id=10,
                latitude_deg=17.0,
                longitude_deg=78.0,
                tags={"man_made": "mast", "name": "Example mast"},
            ),
            OverpassNode(
                osm_id=9,
                latitude_deg=17.1,
                longitude_deg=78.1,
                tags={"man_made": "mast"},
            ),
        ],
        dataset_id="osm-test",
        source_uri="https://overpass-api.de/api/interpreter",
        attribution="Data © OpenStreetMap contributors",
    )
    assert [site.site_id for site in dataset.sites] == ["osm-node-9", "osm-node-10"]
    assert dataset.sites[0].source_type is GroundGeospatialSourceType.OSM


def test_overpass_nodes_require_data() -> None:
    with pytest.raises(ValueError, match="at least one"):
        overpass_nodes_to_dataset(
            [],
            dataset_id="empty",
            source_uri="https://overpass-api.de/api/interpreter",
            attribution="test",
        )
