from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.link import PropagationLosses
from sag_network.domain.models import GeoPoint


class GroundCell(BaseModel):
    """A deterministic terrestrial cell with an explicit radio configuration."""

    cell_id: str = Field(min_length=1)
    position: GeoPoint
    carrier_frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    tx_power_dbm: float
    tx_gain_dbi: float = 0.0
    rx_gain_dbi: float = 0.0
    noise_figure_db: float = Field(ge=0)
    required_sinr_db: float = 0.0
    maximum_service_distance_m: float = Field(gt=0)
    propagation_losses: PropagationLosses
    active: bool = True
    scheduler_efficiency: float = Field(gt=0, le=1.0, default=0.75)


class GroundNetwork(BaseModel):
    """A deterministic collection of terrestrial cells."""

    name: str = Field(min_length=1)
    cells: list[GroundCell] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> GroundNetwork:
        ids = [cell.cell_id for cell in self.cells]
        if len(ids) != len(set(ids)):
            raise ValueError("cell_id values must be unique within a ground network")
        return self


class GroundCandidate(BaseModel):
    """Measured terrestrial candidate state for one user."""

    cell_id: str = Field(min_length=1)
    available: bool
    distance_m: float = Field(gt=0)
    rx_power_dbm: float
    noise_power_dbm: float
    sinr_db: float
    link_margin_db: float
    shannon_capacity_bps: float = Field(ge=0)
    estimated_capacity_bps: float = Field(ge=0)


class GroundUserAssociation(BaseModel):
    """One user's deterministic terrestrial association and scheduled rate ceiling."""

    user_id: str = Field(min_length=1)
    selected_cell_id: str | None = None
    demand_bps: float = Field(ge=0)
    allocated_capacity_bps: float = Field(ge=0)
    candidates: list[GroundCandidate]


class GroundNetworkSnapshot(BaseModel):
    """Multi-user terrestrial network state at one simulation timestamp."""

    timestamp_s: float = Field(ge=0)
    associations: list[GroundUserAssociation]
