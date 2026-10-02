from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NTNEnvironment(StrEnum):
    """Outdoor propagation environment categories used by 3GPP TR 38.811."""

    DENSE_URBAN = "dense_urban"
    URBAN = "urban"
    SUBURBAN_RURAL = "suburban_rural"


class NTNBand(StrEnum):
    """3GPP TR 38.811 large-scale table families used by this implementation."""

    S_BAND = "s_band"
    KA_BAND = "ka_band"


class ChannelCondition(StrEnum):
    LOS = "los"
    NLOS = "nlos"


class FadingDistribution(StrEnum):
    RAYLEIGH = "rayleigh"
    RICIAN = "rician"


class WeatherAttenuation(BaseModel):
    """Site-provided specific attenuation inputs for a slant path.

    The values are deliberately supplied by the scenario rather than pretending to
    implement the full ITU-R atmospheric/rain/cloud prediction algorithms.
    """

    model_config = ConfigDict(extra="forbid")

    gas_specific_db_per_km: float = Field(ge=0, default=0.0)
    rain_specific_db_per_km: float = Field(ge=0, default=0.0)
    cloud_specific_db_per_km: float = Field(ge=0, default=0.0)
    scintillation_db: float = Field(ge=0, default=0.0)
    building_entry_loss_db: float = Field(ge=0, default=0.0)


class NTNChannelConfig(BaseModel):
    """Configurable higher-fidelity NTN channel realization parameters."""

    model_config = ConfigDict(extra="forbid")

    environment: NTNEnvironment = NTNEnvironment.SUBURBAN_RURAL
    band: NTNBand | None = None
    seed: int = 42
    enable_3gpp_large_scale: bool = True
    enable_shadow_fading: bool = True
    enable_small_scale_fading: bool = True
    enable_weather_attenuation: bool = True
    los_correlation_time_s: float = Field(gt=0, default=20.0)
    shadow_decorrelation_distance_m: float = Field(gt=0, default=100.0)
    rician_k_factor_db: float = Field(ge=0, default=10.0)
    weather: WeatherAttenuation = Field(default_factory=WeatherAttenuation)


class NTNChannelContext(BaseModel):
    """Physical link state supplied to the channel realization engine."""

    model_config = ConfigDict(extra="forbid")

    link_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    elevation_deg: float = Field(ge=0, le=90)
    slant_range_m: float = Field(gt=0)
    frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    relative_speed_mps: float = Field(ge=0)


class PowerDelayTap(BaseModel):
    """One optional normalized power-delay component of a channel realization."""

    delay_ns: float = Field(ge=0)
    relative_power_db: float
    distribution: FadingDistribution


class NTNChannelResult(BaseModel):
    """One deterministic, stateful NTN channel realization."""

    model_config = ConfigDict(extra="forbid")

    link_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    elevation_deg: float = Field(ge=0, le=90)
    slant_range_m: float = Field(gt=0)
    frequency_hz: float = Field(gt=0)
    bandwidth_hz: float = Field(gt=0)
    relative_speed_mps: float = Field(ge=0)
    band: NTNBand
    environment: NTNEnvironment
    los_probability: float = Field(ge=0, le=1)
    condition: ChannelCondition
    shadow_sigma_db: float = Field(ge=0)
    shadow_fading_db: float
    clutter_loss_db: float = Field(ge=0)
    gas_loss_db: float = Field(ge=0)
    rain_loss_db: float = Field(ge=0)
    cloud_loss_db: float = Field(ge=0)
    scintillation_loss_db: float = Field(ge=0)
    building_entry_loss_db: float = Field(ge=0)
    deterministic_loss_db: float = Field(ge=0)
    fading_distribution: FadingDistribution
    rician_k_factor_db: float = Field(ge=0)
    small_scale_fading_gain_db: float
    channel_gain_real: float
    channel_gain_imag: float
    coherence_time_s: float | None = Field(default=None, ge=0)
    maximum_doppler_hz: float = Field(ge=0)
    taps: list[PowerDelayTap] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fading_consistency(self) -> NTNChannelResult:
        if self.condition is ChannelCondition.NLOS and self.fading_distribution is FadingDistribution.RICIAN:
            raise ValueError("NLOS condition must use Rayleigh fading in this baseline")
        return self
