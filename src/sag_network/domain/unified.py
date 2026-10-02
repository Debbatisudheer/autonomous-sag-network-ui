from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.air import AirNetwork
from sag_network.domain.constellation import Constellation
from sag_network.domain.ground import GroundNetwork
from sag_network.domain.link import PropagationLosses


class NetworkDomain(str, Enum):
    GROUND = "ground"
    AIR = "air"
    SPACE = "space"


class SatelliteRadioProfile(BaseModel):
    """Shared radio configuration used to evaluate user-to-satellite links."""

    carrier_frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    tx_power_dbm: float
    tx_gain_dbi: float
    rx_gain_dbi: float
    noise_figure_db: float = Field(ge=0)
    propagation_losses: PropagationLosses
    required_sinr_db: float


class UnifiedNetwork(BaseModel):
    """The composed Ground-Air-Space network without duplicating domain models."""

    name: str = Field(min_length=1)
    ground: GroundNetwork
    air: AirNetwork
    space: Constellation
    satellite_radio: SatelliteRadioProfile

    @model_validator(mode="after")
    def validate_resource_ids(self) -> UnifiedNetwork:
        ids: list[str] = [cell.cell_id for cell in self.ground.cells]
        ids.extend(platform.platform_id for platform in self.air.platforms)
        ids.extend(satellite.satellite_id for satellite in self.space.satellites)
        if len(ids) != len(set(ids)):
            raise ValueError("resource identifiers must be unique across Ground, Air, and Space")
        return self


class UnifiedCandidate(BaseModel):
    """Common observable state for one user's candidate network resource."""

    resource_id: str = Field(min_length=1)
    domain: NetworkDomain
    resource_type: str = Field(min_length=1)
    available: bool
    distance_m: float = Field(gt=0)
    rx_power_dbm: float
    noise_power_dbm: float
    sinr_db: float
    link_margin_db: float
    shannon_capacity_bps: float = Field(ge=0)
    estimated_capacity_bps: float = Field(ge=0)
    propagation_delay_ms: float = Field(ge=0)
    doppler_shift_hz: float | None = None
    remaining_energy_wh: float | None = Field(default=None, ge=0)
    time_to_reserve_s: float | None = Field(default=None, ge=0)
    predicted_loss_time_s: float | None = Field(default=None, ge=0)


class UnifiedUserAssociation(BaseModel):
    """A user's common cross-domain connectivity state."""

    user_id: str = Field(min_length=1)
    selected_resource_id: str | None = None
    selected_domain: NetworkDomain | None = None
    demand_bps: float = Field(ge=0)
    allocated_capacity_bps: float = Field(ge=0)
    candidates: list[UnifiedCandidate]


class UnifiedNetworkSnapshot(BaseModel):
    """One synchronized Ground-Air-Space network snapshot."""

    timestamp_s: float = Field(ge=0)
    associations: list[UnifiedUserAssociation]
