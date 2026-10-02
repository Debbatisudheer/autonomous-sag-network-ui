from __future__ import annotations

import json
from pathlib import Path

from sag_network.domain.link import PropagationLosses
from sag_network.geospatial.geojson import load_ground_sites_geojson
from sag_network.geospatial.models import GroundRadioProfile
from sag_network.geospatial.network import build_ground_network_from_sites

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "geospatial" / "ground-reference-india.geojson"


def main() -> None:
    dataset = load_ground_sites_geojson(
        DATASET,
        dataset_id="india-reference-cities-v1",
        source_name="Offline public geospatial reference fixture",
        attribution="Reference coordinates retained for deterministic offline testing",
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
        network_name="india-reference-ground",
    )
    print(
        json.dumps(
            {
                "dataset_id": dataset.dataset_id,
                "source_name": dataset.source_name,
                "site_count": len(dataset.sites),
                "site_ids": [site.site_id for site in dataset.sites],
                "fingerprint": dataset.fingerprint,
                "ground_network_cells": len(network.cells),
                "radio_profile": {
                    "frequency_hz": 3.5e9,
                    "bandwidth_hz": 20e6,
                },
                "status": "pass",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
