from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryQuality, TelemetryRecord


class HistoricalDatasetStatus(str, Enum):
    """Lifecycle state of a historical dataset artifact."""

    BUILDING = "building"
    SEALED = "sealed"


class HistoricalDatasetConfig(BaseModel):
    """Deterministic storage and retention boundaries for historical telemetry."""

    partition_span_s: float = Field(default=3600.0, gt=0)
    allow_duplicate_record_ids: bool = False


class HistoricalQuery(BaseModel):
    """Deterministic filters for historical telemetry retrieval."""

    start_time_s: float | None = Field(default=None, ge=0)
    end_time_s: float | None = Field(default=None, ge=0)
    source_ids: tuple[str, ...] = ()
    domains: tuple[NetworkDomain, ...] = ()
    metrics: tuple[str, ...] = ()
    qualities: tuple[TelemetryQuality, ...] = ()
    limit: int | None = Field(default=None, ge=1)

    def validate_window(self) -> None:
        if (
            self.start_time_s is not None
            and self.end_time_s is not None
            and self.end_time_s < self.start_time_s
        ):
            raise ValueError("end_time_s must be greater than or equal to start_time_s")


class HistoricalDatasetManifest(BaseModel):
    """Reproducible manifest describing one historical dataset artifact."""

    dataset_id: str = Field(min_length=1)
    schema_version: str = Field(default="1", min_length=1)
    status: HistoricalDatasetStatus
    record_count: int = Field(ge=0)
    partition_count: int = Field(ge=0)
    min_timestamp_s: float | None = Field(default=None, ge=0)
    max_timestamp_s: float | None = Field(default=None, ge=0)
    source_count: int = Field(ge=0)
    source_fingerprints: tuple[str, ...] = ()
    partition_fingerprints: tuple[str, ...] = ()
    dataset_fingerprint: str = Field(min_length=64, max_length=64)


class HistoricalQueryResult(BaseModel):
    """Deterministic historical query result with dataset identity."""

    dataset_id: str = Field(min_length=1)
    records: list[TelemetryRecord]
    dataset_fingerprint: str = Field(min_length=64, max_length=64)

    @property
    def count(self) -> int:
        return len(self.records)
