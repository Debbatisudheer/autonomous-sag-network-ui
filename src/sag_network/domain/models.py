from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    USER = "user"
    GROUND_STATION = "ground_station"
    UAV = "uav"
    HAPS = "haps"
    LEO_SATELLITE = "leo_satellite"


class GeoPoint(BaseModel):
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)
    altitude_m: float = Field(ge=0)


class NetworkNode(BaseModel):
    node_id: str = Field(min_length=1)
    node_type: NodeType
    position: GeoPoint
    available_capacity_bps: float = Field(ge=0)
    tx_power_dbm: float
    tx_gain_dbi: float = 0
    rx_gain_dbi: float = 0
    active: bool = True


class LinkObservation(BaseModel):
    timestamp_s: float = Field(ge=0)
    source_id: str
    target_id: str
    distance_m: float = Field(gt=0)
    rx_power_dbm: float
    noise_power_dbm: float
    sinr_db: float
    latency_ms: float = Field(ge=0)
    available_bps: float = Field(ge=0)
    visible: bool


class SimulationConfig(BaseModel):
    seed: int = 42
    duration_seconds: int = Field(gt=0)
    step_seconds: int = Field(gt=0)


class EnvironmentConfig(BaseModel):
    frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    noise_figure_db: float = Field(ge=0)
    tx_power_dbm: float
    tx_gain_dbi: float
    rx_gain_dbi: float
