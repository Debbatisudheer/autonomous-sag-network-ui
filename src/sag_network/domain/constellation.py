from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.space import OrbitalElements


class SatelliteDefinition(BaseModel):
    """A configured satellite represented by orbital elements and an identifier."""

    satellite_id: str = Field(min_length=1)
    orbital_elements: OrbitalElements
    minimum_elevation_deg: float = Field(default=10.0, ge=0.0, le=90.0)
    active: bool = True


class Constellation(BaseModel):
    """A deterministic collection of configured satellites."""

    name: str = Field(min_length=1)
    satellites: list[SatelliteDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Constellation:
        ids = [satellite.satellite_id for satellite in self.satellites]
        if len(ids) != len(set(ids)):
            raise ValueError("satellite_id values must be unique within a constellation")
        return self


class SatellitePass(BaseModel):
    """A predicted ground-station visibility window for one satellite."""

    satellite_id: str = Field(min_length=1)
    aos_s: float = Field(ge=0)
    max_elevation_s: float = Field(ge=0)
    max_elevation_deg: float
    los_s: float = Field(ge=0)

    @property
    def duration_s(self) -> float:
        return self.los_s - self.aos_s
