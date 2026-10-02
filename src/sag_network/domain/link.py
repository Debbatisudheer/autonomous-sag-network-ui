from __future__ import annotations

from pydantic import BaseModel, Field


class PropagationLosses(BaseModel):
    """Explicit non-FSPL losses in a radio link budget, all in dB."""

    atmospheric_db: float = Field(ge=0)
    rain_db: float = Field(ge=0)
    polarization_db: float = Field(ge=0)
    implementation_db: float = Field(ge=0)

    @property
    def total_db(self) -> float:
        return (
            self.atmospheric_db
            + self.rain_db
            + self.polarization_db
            + self.implementation_db
        )


class LinkBudget(BaseModel):
    """Calculated link budget and performance indicators."""

    distance_m: float = Field(gt=0)
    frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    free_space_path_loss_db: float
    additional_path_loss_db: float = Field(ge=0)
    total_path_loss_db: float = Field(ge=0)
    rx_power_dbm: float
    noise_power_dbm: float
    interference_power_dbm: float | None = None
    sinr_db: float
    shannon_capacity_bps: float = Field(ge=0)
    required_sinr_db: float
    link_margin_db: float
    available: bool
