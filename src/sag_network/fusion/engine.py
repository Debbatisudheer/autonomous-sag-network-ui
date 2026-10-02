from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from sag_network.telemetry.models import TelemetryQuality, TelemetryRecord


class FusionError(ValueError):
    """Raised when telemetry sources cannot be fused safely."""


@dataclass(frozen=True)
class FusionConfig:
    """Deterministic boundaries for multi-source telemetry reconciliation."""

    timestamp_tolerance_s: float = 1.0
    minimum_sources: int = 2

    def __post_init__(self) -> None:
        if self.timestamp_tolerance_s < 0:
            raise ValueError("timestamp_tolerance_s must be non-negative")
        if self.minimum_sources < 1:
            raise ValueError("minimum_sources must be at least one")


@dataclass(frozen=True)
class FusedTelemetry:
    """One reconciled observation produced from temporally aligned sources."""

    fusion_id: str
    source_id: str
    domain: str
    metric: str
    unit: str
    timestamp_s: float
    value: float
    source_count: int
    source_names: tuple[str, ...]
    record_ids: tuple[str, ...]
    spread: float
    quality: TelemetryQuality
    provenance_fingerprints: tuple[str, ...]


@dataclass(frozen=True)
class MultiSourceFusionReport:
    """Deterministic summary of a multi-source fusion run."""

    input_record_count: int
    source_count: int
    provenance_source_count: int
    fused_record_count: int
    unresolved_record_count: int
    conflict_count: int
    source_names: tuple[str, ...]
    fused: tuple[FusedTelemetry, ...]
    fingerprint: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, default=str)


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _provenance_name(record: TelemetryRecord) -> str:
    return record.metadata.get("provenance_source", "unknown")


def _provenance_fingerprint(record: TelemetryRecord) -> str:
    return record.metadata.get("provenance_sha256", "unknown")


def _quality(records: list[TelemetryRecord]) -> TelemetryQuality:
    qualities = {record.quality for record in records}
    if TelemetryQuality.INVALID in qualities:
        return TelemetryQuality.INVALID
    if TelemetryQuality.DEGRADED in qualities:
        return TelemetryQuality.DEGRADED
    return TelemetryQuality.GOOD


def fuse_telemetry(
    records: Iterable[TelemetryRecord],
    *,
    config: FusionConfig | None = None,
) -> MultiSourceFusionReport:
    """Fuse aligned observations without silently combining incompatible metrics."""
    settings = config or FusionConfig()
    ordered = sorted(
        records,
        key=lambda record: (
            record.source_id,
            record.domain.value,
            record.metric.value,
            record.unit,
            record.timestamp_s,
            record.sequence,
            record.record_id,
        ),
    )

    if not ordered:
        raise FusionError("at least one telemetry record is required")

    groups: dict[tuple[str, str, str, str], list[list[TelemetryRecord]]] = defaultdict(list)
    for record in ordered:
        key = (
            record.source_id,
            record.domain.value,
            record.metric.value,
            record.unit,
        )
        candidates = groups[key]
        if not candidates or record.timestamp_s - candidates[-1][-1].timestamp_s > settings.timestamp_tolerance_s:
            candidates.append([record])
        else:
            candidates[-1].append(record)

    fused: list[FusedTelemetry] = []
    unresolved = 0
    conflicts = 0

    for key, clusters in sorted(groups.items()):
        for cluster in clusters:
            provenance_names = tuple(sorted({_provenance_name(record) for record in cluster}))
            provenance_fingerprints = tuple(
                sorted({_provenance_fingerprint(record) for record in cluster})
            )
            if len(provenance_names) < settings.minimum_sources:
                unresolved += 1
                continue

            values = [record.value for record in cluster]
            mean_value = sum(values) / len(values)
            spread = max(values) - min(values)
            if spread > 0:
                conflicts += 1

            timestamp = sum(record.timestamp_s for record in cluster) / len(cluster)
            record_ids = tuple(sorted(record.record_id for record in cluster))
            fusion_id = _fingerprint(
                {
                    "key": key,
                    "record_ids": record_ids,
                    "provenance": provenance_fingerprints,
                }
            )[:24]
            fused.append(
                FusedTelemetry(
                    fusion_id=fusion_id,
                    source_id=key[0],
                    domain=key[1],
                    metric=key[2],
                    unit=key[3],
                    timestamp_s=timestamp,
                    value=mean_value,
                    source_count=len(provenance_names),
                    source_names=provenance_names,
                    record_ids=record_ids,
                    spread=spread,
                    quality=_quality(cluster),
                    provenance_fingerprints=provenance_fingerprints,
                )
            )

    source_names = tuple(sorted({_provenance_name(record) for record in ordered}))
    fingerprint = _fingerprint(
        {
            "input_record_count": len(ordered),
            "source_count": len({record.source_id for record in ordered}),
            "provenance_source_count": len(source_names),
            "fused_record_count": len(fused),
            "unresolved_record_count": unresolved,
            "conflict_count": conflicts,
            "source_names": source_names,
            "fused": [asdict(item) for item in fused],
        }
    )
    return MultiSourceFusionReport(
        input_record_count=len(ordered),
        source_count=len({record.source_id for record in ordered}),
        provenance_source_count=len(source_names),
        fused_record_count=len(fused),
        unresolved_record_count=unresolved,
        conflict_count=conflicts,
        source_names=source_names,
        fused=tuple(fused),
        fingerprint=fingerprint,
    )
