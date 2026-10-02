from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelEffectProfile(BaseModel):
    """Explicit deterministic channel impairments applied after the baseline link budget."""

    additional_loss_db: float = Field(ge=0, default=0.0)


class InterferenceSource(BaseModel):
    """A configurable co-channel or partially overlapping interferer."""

    source_id: str = Field(min_length=1)
    carrier_frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    distance_m: float = Field(gt=0)
    tx_power_dbm: float
    tx_gain_dbi: float = 0.0
    rx_gain_dbi: float = 0.0
    additional_path_loss_db: float = Field(ge=0, default=0.0)
    coupling_loss_db: float = Field(ge=0, default=0.0)
    activity_factor: float = Field(ge=0, le=1.0, default=1.0)
    active: bool = True


class InterferenceContribution(BaseModel):
    """One interferer's contribution at the desired receiver."""

    source_id: str = Field(min_length=1)
    overlap_fraction: float = Field(ge=0, le=1)
    received_power_dbm: float
    effective_power_dbm: float | None = None


class InterferenceEvaluation(BaseModel):
    """Aggregate interference and resulting link metrics at one simulation instant."""

    desired_rx_power_dbm: float
    noise_power_dbm: float
    aggregate_interference_power_dbm: float | None
    sinr_db: float
    shannon_capacity_bps: float = Field(ge=0)
    interference_degradation_db: float
    contributions: list[InterferenceContribution]
