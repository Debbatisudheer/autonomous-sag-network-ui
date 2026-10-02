from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.unified import NetworkDomain


class TelemetryMetric(str, Enum):
    """Normalized machine-readable telemetry metric identifiers."""

    AVAILABLE = "available"
    CAPACITY_BPS = "capacity_bps"
    DOPPLER_SHIFT_HZ = "doppler_shift_hz"
    INTERFERENCE_POWER_DBM = "interference_power_dbm"
    LATENCY_MS = "latency_ms"
    LINK_MARGIN_DB = "link_margin_db"
    NOISE_POWER_DBM = "noise_power_dbm"
    RECEIVED_POWER_DBM = "received_power_dbm"
    REMAINING_ENERGY_WH = "remaining_energy_wh"
    RESOURCE_REMAINING_CAPACITY_BPS = "resource_remaining_capacity_bps"
    RESOURCE_SCHEDULED_CAPACITY_BPS = "resource_scheduled_capacity_bps"
    RESOURCE_UTILIZATION_RATIO = "resource_utilization_ratio"
    SINR_DB = "sinr_db"


class TelemetryQuality(str, Enum):
    """Quality assigned by the telemetry producer or validator."""

    GOOD = "good"
    DEGRADED = "degraded"
    INVALID = "invalid"


class TelemetryRecord(BaseModel):
    """One timestamped normalized telemetry observation."""

    record_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    sequence: int = Field(ge=0)
    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    value: float
    unit: str = Field(min_length=1)
    quality: TelemetryQuality = TelemetryQuality.GOOD
    metadata: dict[str, str] = Field(default_factory=dict)


class TelemetryBatch(BaseModel):
    """A deterministic group of telemetry records produced at one collection boundary."""

    batch_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    records: list[TelemetryRecord]
    source: str = Field(min_length=1, default="simulation")
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record_timestamps(self) -> TelemetryBatch:
        for record in self.records:
            if record.timestamp_s > self.timestamp_s:
                raise ValueError("telemetry record timestamp must not exceed batch timestamp")
        return self


class TelemetryRejection(BaseModel):
    """A telemetry record rejected by the ingestion boundary."""

    record_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class TelemetryIngestResult(BaseModel):
    """Deterministic outcome of one telemetry ingestion operation."""

    accepted_record_ids: list[str] = Field(default_factory=list)
    rejected_records: list[TelemetryRejection] = Field(default_factory=list)
    state_updates: int = Field(ge=0)

    @property
    def accepted_count(self) -> int:
        return len(self.accepted_record_ids)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_records)


class TelemetryStateSample(BaseModel):
    """Latest known value for one normalized source/metric key."""

    source_id: str = Field(min_length=1)
    domain: NetworkDomain
    metric: TelemetryMetric
    value: float
    unit: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    sequence: int = Field(ge=0)
    age_s: float = Field(ge=0)
    quality: TelemetryQuality
    stale: bool
    metadata: dict[str, str] = Field(default_factory=dict)


class RealTimeStateSnapshot(BaseModel):
    """Point-in-time read model built from the latest ingested telemetry."""

    timestamp_s: float = Field(ge=0)
    samples: list[TelemetryStateSample]

    @property
    def sample_count(self) -> int:
        return len(self.samples)

    @property
    def stale_sample_count(self) -> int:
        return sum(sample.stale for sample in self.samples)


class TelemetryIngestionConfig(BaseModel):
    """Boundaries for deterministic telemetry ingestion and retention."""

    history_limit: int = Field(default=1000, ge=1)
    stale_after_s: float = Field(default=5.0, ge=0)
    reject_future_records: bool = True
    max_future_skew_s: float = Field(default=0.0, ge=0)
    enforce_monotonic_sequence: bool = True
    enforce_monotonic_timestamp: bool = True


class TelemetryTwinLink(BaseModel):
    """Explicit alignment record connecting telemetry state to a digital-twin snapshot."""

    twin_snapshot_id: str = Field(min_length=1)
    twin_timestamp_s: float = Field(ge=0)
    telemetry_timestamp_s: float = Field(ge=0)
    sample_count: int = Field(ge=0)
    stale_sample_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_alignment(self) -> TelemetryTwinLink:
        if self.twin_timestamp_s != self.telemetry_timestamp_s:
            raise ValueError("digital twin and telemetry timestamps must match")
        if self.stale_sample_count > self.sample_count:
            raise ValueError("stale_sample_count must not exceed sample_count")
        return self
