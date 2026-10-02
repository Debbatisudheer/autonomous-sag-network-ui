from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CartesianPoint(BaseModel):
    """Three-dimensional Cartesian position in a named reference frame."""

    x_m: float
    y_m: float
    z_m: float


class OrbitalElements(BaseModel):
    semi_major_axis_m: float = Field(gt=6_378_137.0)
    eccentricity: float = Field(ge=0.0, lt=1.0)
    inclination_deg: float = Field(ge=0.0, le=180.0)
    raan_deg: float
    argument_of_perigee_deg: float
    mean_anomaly_deg: float

    @model_validator(mode="after")
    def validate_orbit(self) -> OrbitalElements:
        perigee_radius_m = self.semi_major_axis_m * (1 - self.eccentricity)
        if self.eccentricity > 0 and perigee_radius_m <= 6_378_137.0:
            raise ValueError("perigee altitude must remain above the WGS84 equatorial radius")
        return self


class SatelliteState(BaseModel):
    timestamp_s: float = Field(ge=0)
    position_eci: CartesianPoint
    position_ecef: CartesianPoint
    velocity_eci: CartesianPoint
    velocity_ecef: CartesianPoint


class GroundSatelliteVisibility(BaseModel):
    timestamp_s: float = Field(ge=0)
    ground_station_id: str = Field(min_length=1)
    elevation_deg: float
    slant_range_m: float = Field(gt=0)
    visible: bool
