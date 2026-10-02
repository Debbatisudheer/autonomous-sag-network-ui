from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from sag_network.domain.models import GeoPoint


class GroundGeospatialSourceType(StrEnum):
    OSM = "openstreetmap"
    GEOJSON = "geojson"
    USGS_3DEP = "usgs_3dep"
    MANUAL = "manual"


class GroundSiteRecord(BaseModel):
    """A real-world ground site with provenance and geospatial coordinates."""

    site_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    position: GeoPoint
    source_type: GroundGeospatialSourceType
    source_uri: str = Field(min_length=1)
    source_feature_id: str | None = None
    feature_type: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class GroundSiteDataset(BaseModel):
    """Validated set of ground sites plus data provenance."""

    dataset_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    retrieved_at_utc: datetime | None = None
    sites: list[GroundSiteRecord] = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64)


class GroundRadioProfile(BaseModel):
    """Common radio parameters used when turning geospatial sites into GroundCell objects."""

    carrier_frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    tx_power_dbm: float
    tx_gain_dbi: float = 0.0
    rx_gain_dbi: float = 0.0
    noise_figure_db: float = Field(ge=0)
    required_sinr_db: float = 0.0
    maximum_service_distance_m: float = Field(gt=0)
    scheduler_efficiency: float = Field(gt=0, le=1.0, default=0.75)


class GroundElevationRecord(BaseModel):
    """Elevation observation attached to a real ground coordinate."""

    site_id: str = Field(min_length=1)
    elevation_m: float
    source_type: GroundGeospatialSourceType
    source_uri: str = Field(min_length=1)
    retrieved_at_utc: datetime | None = None


class GroundSiteEnrichment(BaseModel):
    """One site after optional elevation enrichment."""

    site: GroundSiteRecord
    elevation: GroundElevationRecord | None = None


class GroundGeospatialDatasetManifest(BaseModel):
    """Reproducibility metadata for an ingested ground dataset."""

    dataset_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    record_count: int = Field(gt=0)
    fingerprint: str = Field(min_length=64, max_length=64)
    retrieved_at_utc: datetime | None = None
