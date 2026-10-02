from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationRejection:
    """One telemetry record rejected before it reaches the ingestion state store."""

    record_id: str
    reason: str


@dataclass(frozen=True)
class TelemetryValidationReport:
    """Deterministic summary of a real-time telemetry validation pass."""

    input_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    rejection_reasons: dict[str, int]
    accepted_record_ids: tuple[str, ...]
    rejected_record_ids: tuple[str, ...]
    validation_fingerprint: str
