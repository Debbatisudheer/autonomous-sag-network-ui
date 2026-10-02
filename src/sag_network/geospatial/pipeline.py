from __future__ import annotations

from datetime import datetime, UTC

from sag_network.domain.ground import GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.geospatial.models import (
    GroundElevationRecord,
    GroundGeospatialSourceType,
    GroundRadioProfile,
    GroundSiteDataset,
    GroundSiteEnrichment,
)
from sag_network.geospatial.network import build_ground_network_from_sites


def enrich_sites_with_elevation(
    dataset: GroundSiteDataset,
    elevations: dict[str, float],
    *,
    source_uri: str,
) -> list[GroundSiteEnrichment]:
    """Attach externally measured elevation values without mutating site coordinates."""
    timestamp = datetime.now(UTC)
    enriched: list[GroundSiteEnrichment] = []
    for site in sorted(dataset.sites, key=lambda item: item.site_id):
        value = elevations.get(site.site_id)
        record = None
        if value is not None:
            record = GroundElevationRecord(
                site_id=site.site_id,
                elevation_m=float(value),
                source_type=GroundGeospatialSourceType.USGS_3DEP,
                source_uri=source_uri,
                retrieved_at_utc=timestamp,
            )
        enriched.append(GroundSiteEnrichment(site=site, elevation=record))
    return enriched


def build_network_from_geospatial_data(
    dataset: GroundSiteDataset,
    *,
    radio_profile: GroundRadioProfile,
    propagation_losses: PropagationLosses,
    network_name: str,
) -> GroundNetwork:
    return build_ground_network_from_sites(
        dataset,
        radio_profile=radio_profile,
        propagation_losses=propagation_losses,
        network_name=network_name,
    )
