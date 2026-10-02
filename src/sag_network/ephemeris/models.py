from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EphemerisSourceType(StrEnum):
    TLE = "tle"
    OMM = "omm"


class TLERecord(BaseModel):
    """Validated two-line element set with provenance metadata."""

    satellite_name: str = Field(min_length=1)
    line1: str = Field(min_length=69, max_length=69)
    line2: str = Field(min_length=69, max_length=69)
    source: str = Field(min_length=1)
    retrieved_at_utc: datetime | None = None

    @property
    def norad_catalog_id(self) -> int:
        return int(self.line1[2:7].strip())

    @property
    def epoch_year(self) -> int:
        year = int(self.line1[18:20])
        return 2000 + year if year < 57 else 1900 + year

    @property
    def epoch_day_of_year(self) -> float:
        return float(self.line1[20:32])


class OMMRecord(BaseModel):
    """Subset of CCSDS OMM fields needed to initialize an SGP4 record."""

    model_config = ConfigDict(populate_by_name=True)

    object_name: str = Field(min_length=1, alias="OBJECT_NAME")
    object_id: str | None = Field(default=None, alias="OBJECT_ID")
    norad_cat_id: int | None = Field(default=None, alias="NORAD_CAT_ID")
    epoch: str = Field(min_length=1, alias="EPOCH")
    mean_motion: float = Field(gt=0, alias="MEAN_MOTION")
    eccentricity: float = Field(ge=0, lt=1, alias="ECCENTRICITY")
    inclination: float = Field(ge=0, le=180, alias="INCLINATION")
    ra_of_asc_node: float = Field(alias="RA_OF_ASC_NODE")
    arg_of_pericenter: float = Field(alias="ARG_OF_PERICENTER")
    mean_anomaly: float = Field(alias="MEAN_ANOMALY")
    mean_motion_dot: float = Field(default=0.0, alias="MEAN_MOTION_DOT")
    mean_motion_ddot: float = Field(default=0.0, alias="MEAN_MOTION_DDOT")
    bstar: float | None = Field(default=None, alias="BSTAR")
    mean_element_theory: str = Field(default="SGP4", alias="MEAN_ELEMENT_THEORY")
    ref_frame: str = Field(default="TEME", alias="REF_FRAME")
    time_system: str = Field(default="UTC", alias="TIME_SYSTEM")

    def to_sgp4_fields(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, exclude_none=True)


class RealSatelliteState(BaseModel):
    """Absolute state produced from a real ephemeris record and SGP4."""

    satellite_id: str = Field(min_length=1)
    timestamp_utc: datetime
    source_type: EphemerisSourceType
    source_epoch_utc: datetime
    elapsed_since_epoch_s: float
    position_teme_km: tuple[float, float, float]
    velocity_teme_km_s: tuple[float, float, float]
    position_ecef_m: tuple[float, float, float]
    velocity_ecef_m_s: tuple[float, float, float]
    sgp4_error_code: int = 0
    propagation_model: str = "SGP4"
    reference_frame: str = "TEME"


class RealSatelliteDefinition(BaseModel):
    """A satellite backed by an external real ephemeris provider."""

    satellite_id: str = Field(min_length=1)
    source_type: EphemerisSourceType
    minimum_elevation_deg: float = Field(default=10.0, ge=0.0, le=90.0)
    active: bool = True


class EphemerisSimulationConfig(BaseModel):
    """Maps a relative simulation clock to an absolute UTC epoch."""

    simulation_epoch_utc: datetime
    max_propagation_age_s: float = Field(default=7.0 * 86_400.0, gt=0)
