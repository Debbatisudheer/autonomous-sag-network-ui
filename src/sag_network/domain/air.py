from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint


class AirPlatformType(str, Enum):
    UAV = "uav"
    HAPS = "haps"


class AirPlatform(BaseModel):
    """Configurable aerial communication platform with deterministic mobility and energy state."""

    platform_id: str = Field(min_length=1)
    platform_type: AirPlatformType
    initial_position: GeoPoint
    mobility: MobilityProfile = Field(default_factory=MobilityProfile)
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
    initial_energy_wh: float = Field(gt=0)
    reserve_energy_wh: float = Field(ge=0, default=0.0)
    hotel_power_w: float = Field(gt=0)
    propulsion_power_w: float = Field(ge=0, default=0.0)

    @model_validator(mode="after")
    def validate_energy_reserve(self) -> AirPlatform:
        if self.reserve_energy_wh >= self.initial_energy_wh:
            raise ValueError("reserve_energy_wh must be less than initial_energy_wh")
        if self.platform_type is AirPlatformType.HAPS and self.mobility.horizontal_speed_mps > 0:
            raise ValueError("HAPS baseline is fixed; horizontal mobility must be zero")
        if self.platform_type is AirPlatformType.HAPS and self.mobility.vertical_velocity_mps != 0:
            raise ValueError("HAPS baseline is fixed; vertical mobility must be zero")
        return self

    def position_at(self, timestamp_s: float) -> GeoPoint:
        """Return the aerial platform geodetic position at a simulation timestamp."""
        mobile_user = MobileUser(
            user_id=self.platform_id,
            initial_position=self.initial_position,
            mobility=self.mobility,
            active=self.active,
        )
        return mobile_user.position_at(timestamp_s)

    @property
    def total_power_w(self) -> float:
        return self.hotel_power_w + self.propulsion_power_w

    def energy_remaining_wh(self, timestamp_s: float) -> float:
        """Calculate remaining onboard energy under the configured deterministic power model."""
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")
        consumed_wh = self.total_power_w * timestamp_s / 3600.0
        return max(self.initial_energy_wh - consumed_wh, 0.0)

    def energy_available(self, timestamp_s: float) -> bool:
        """Return whether the platform remains above its configured reserve."""
        return self.energy_remaining_wh(timestamp_s) > self.reserve_energy_wh

    def time_to_reserve_s(self, timestamp_s: float) -> float | None:
        """Return seconds until reserve energy is reached from the current simulation time."""
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")
        if not self.energy_available(timestamp_s):
            return 0.0
        if self.total_power_w <= 0:
            return None
        remaining_until_reserve_wh = self.energy_remaining_wh(timestamp_s) - self.reserve_energy_wh
        return remaining_until_reserve_wh * 3600.0 / self.total_power_w


class AirNetwork(BaseModel):
    """A deterministic collection of aerial communication platforms."""

    name: str = Field(min_length=1)
    platforms: list[AirPlatform] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> AirNetwork:
        ids = [platform.platform_id for platform in self.platforms]
        if len(ids) != len(set(ids)):
            raise ValueError("platform_id values must be unique within an air network")
        return self


class AirCandidate(BaseModel):
    """Measured aerial candidate state for one mobile user."""

    platform_id: str = Field(min_length=1)
    platform_type: AirPlatformType
    available: bool
    distance_m: float = Field(gt=0)
    rx_power_dbm: float
    noise_power_dbm: float
    sinr_db: float
    link_margin_db: float
    shannon_capacity_bps: float = Field(ge=0)
    estimated_capacity_bps: float = Field(ge=0)
    remaining_energy_wh: float = Field(ge=0)
    time_to_reserve_s: float | None = Field(default=None, ge=0)


class AirUserAssociation(BaseModel):
    """One user's deterministic aerial association and scheduled rate ceiling."""

    user_id: str = Field(min_length=1)
    selected_platform_id: str | None = None
    demand_bps: float = Field(ge=0)
    allocated_capacity_bps: float = Field(ge=0)
    candidates: list[AirCandidate]


class AirNetworkSnapshot(BaseModel):
    """Multi-user aerial network state at one simulation timestamp."""

    timestamp_s: float = Field(ge=0)
    associations: list[AirUserAssociation]
