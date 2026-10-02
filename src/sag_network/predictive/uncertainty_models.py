from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric


class UncertaintyStatus(str, Enum):
    """Outcome of uncertainty calibration for one telemetry series."""

    CALIBRATED = "calibrated"
    INSUFFICIENT_CALIBRATION = "insufficient_calibration"
    INSUFFICIENT_HISTORY = "insufficient_history"


class UncertaintyConfig(BaseModel):
    """Deterministic configuration for conformal-style forecast intervals."""

    confidence_level: float = Field(default=0.90, gt=0.5, lt=1.0)
    minimum_calibration_samples: int = Field(default=5, ge=1, le=1000)
    horizon_growth: float = Field(default=0.15, ge=0.0, le=2.0)


class UncertaintyInterval(BaseModel):
    """Point forecast and calibrated prediction interval for one horizon."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    forecast_timestamp_s: float = Field(ge=0)
    horizon_s: float = Field(ge=0)
    predicted_value: float
    lower_bound: float
    upper_bound: float
    interval_width: float = Field(ge=0)
    confidence_level: float = Field(gt=0.5, lt=1.0)
    uncertainty_score: float = Field(ge=0, le=1)
    calibration_residual_quantile: float = Field(ge=0)
    model_fingerprint: str = Field(min_length=64, max_length=64)


class UncertaintySeries(BaseModel):
    """Uncertainty-calibrated forecasts for one telemetry series."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    status: UncertaintyStatus
    calibration_samples: int = Field(ge=0)
    calibration_quantile: float | None = Field(default=None, ge=0)
    intervals: list[UncertaintyInterval] = Field(default_factory=list)
    reason: str | None = None


class UncertaintyReport(BaseModel):
    """Deterministic Phase 34 uncertainty calibration report."""

    timestamp_s: float = Field(ge=0)
    config: UncertaintyConfig
    series: list[UncertaintySeries] = Field(default_factory=list)

    @property
    def calibrated_count(self) -> int:
        return sum(item.status is UncertaintyStatus.CALIBRATED for item in self.series)
