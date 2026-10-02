from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, UTC
from io import TextIOBase
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import (
    TelemetryMetric,
    TelemetryQuality,
    TelemetryRecord,
)


class TelemetryAdapterError(ValueError):
    """Raised when an external telemetry source cannot be normalized."""


@dataclass(frozen=True)
class TelemetryTimeMapper:
    """Map absolute UTC timestamps onto a deterministic simulation clock."""

    epoch_utc: datetime
    simulation_epoch_s: float = 0.0

    def __post_init__(self) -> None:
        if self.epoch_utc.tzinfo is None:
            raise ValueError("epoch_utc must be timezone-aware")

    def to_simulation_time(self, timestamp: datetime) -> float:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return self.simulation_epoch_s + (
            timestamp.astimezone(UTC) - self.epoch_utc.astimezone(UTC)
        ).total_seconds()

    def parse_timestamp(self, value: str) -> datetime:
        text = value.strip()
        try:
            return datetime.fromtimestamp(float(text), tz=UTC)
        except ValueError:
            pass
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)


@dataclass(frozen=True)
class TelemetryProvenance:
    """Deterministic identity and origin metadata for an external source."""

    source_name: str
    source_uri: str | None
    content_sha256: str
    schema: str
    external: bool = True

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        *,
        source_name: str,
        schema: str,
        source_uri: str | None = None,
        external: bool = True,
    ) -> TelemetryProvenance:
        return cls(
            source_name=source_name,
            source_uri=source_uri,
            content_sha256=hashlib.sha256(content).hexdigest(),
            schema=schema,
            external=external,
        )

    def metadata(self) -> dict[str, str]:
        result = {
            "provenance_source": self.source_name,
            "provenance_sha256": self.content_sha256,
            "provenance_schema": self.schema,
            "provenance_external": str(self.external).lower(),
        }
        if self.source_uri is not None:
            result["provenance_uri"] = self.source_uri
        return result


@dataclass(frozen=True)
class TelemetrySchema:
    """Explicit CSV/JSON field mapping; adapters never guess column positions."""

    timestamp: str
    value: str
    source_id: str
    metric: str | None = None
    domain: str | None = None
    unit: str | None = None
    sequence: str | None = None
    quality: str | None = None
    record_id: str | None = None


def _domain(value: str) -> NetworkDomain:
    try:
        return NetworkDomain(value.strip().lower())
    except ValueError as exc:
        raise TelemetryAdapterError(f"unsupported network domain: {value!r}") from exc


def _metric(value: str) -> TelemetryMetric:
    try:
        return TelemetryMetric(value.strip().lower())
    except ValueError as exc:
        raise TelemetryAdapterError(f"unsupported telemetry metric: {value!r}") from exc


def _quality(value: str | None) -> TelemetryQuality:
    if not value:
        return TelemetryQuality.GOOD
    try:
        return TelemetryQuality(value.strip().lower())
    except ValueError as exc:
        raise TelemetryAdapterError(f"unsupported telemetry quality: {value!r}") from exc


def _parse_sequence(value: str | None, fallback: int) -> int:
    if value is None or value.strip() == "":
        return fallback
    parsed = int(value)
    if parsed < 0:
        raise TelemetryAdapterError("sequence must be non-negative")
    return parsed


def _record(
    row: Mapping[str, str],
    *,
    row_number: int,
    schema: TelemetrySchema,
    time_mapper: TelemetryTimeMapper,
    provenance: TelemetryProvenance,
    default_domain: NetworkDomain,
    default_metric: TelemetryMetric | None = None,
    default_unit: str = "unknown",
) -> TelemetryRecord:
    try:
        timestamp = time_mapper.parse_timestamp(row[schema.timestamp])
        source_id = row[schema.source_id].strip()
        value = float(row[schema.value])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelemetryAdapterError(f"invalid telemetry row {row_number}: {exc}") from exc
    if not source_id:
        raise TelemetryAdapterError(f"invalid telemetry row {row_number}: source_id is empty")
    metric_value = row[schema.metric].strip() if schema.metric else None
    metric = _metric(metric_value) if metric_value else default_metric
    if metric is None:
        raise TelemetryAdapterError(f"invalid telemetry row {row_number}: metric is required")
    domain = _domain(row[schema.domain]) if schema.domain else default_domain
    unit = row[schema.unit].strip() if schema.unit else default_unit
    if not unit:
        raise TelemetryAdapterError(f"invalid telemetry row {row_number}: unit is empty")
    sequence = _parse_sequence(
        row[schema.sequence] if schema.sequence else None,
        row_number - 1,
    )
    record_id = (
        row[schema.record_id].strip()
        if schema.record_id and row.get(schema.record_id)
        else f"{provenance.content_sha256[:16]}:{row_number}"
    )
    metadata = provenance.metadata()
    metadata["source_row"] = str(row_number)
    metadata["source_timestamp_utc"] = timestamp.isoformat()
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=time_mapper.to_simulation_time(timestamp),
        sequence=sequence,
        source_id=source_id,
        domain=domain,
        metric=metric,
        value=value,
        unit=unit,
        quality=_quality(row[schema.quality] if schema.quality else None),
        metadata=metadata,
    )


class CSVTelemetryAdapter:
    """Stream CSV rows into the existing normalized TelemetryRecord contract."""

    def __init__(
        self,
        *,
        schema: TelemetrySchema,
        time_mapper: TelemetryTimeMapper,
        source_name: str = "CSV telemetry",
        source_uri: str | None = None,
        default_domain: NetworkDomain = NetworkDomain.SPACE,
        default_metric: TelemetryMetric | None = None,
        default_unit: str = "unknown",
    ) -> None:
        self.schema = schema
        self.time_mapper = time_mapper
        self.source_name = source_name
        self.source_uri = source_uri
        self.default_domain = default_domain
        self.default_metric = default_metric
        self.default_unit = default_unit

    def iter_records(self, stream: TextIOBase) -> Iterator[TelemetryRecord]:
        content = stream.read()
        provenance = TelemetryProvenance.from_bytes(
            content.encode("utf-8"),
            source_name=self.source_name,
            source_uri=self.source_uri,
            schema="csv",
            external=self.source_uri is not None,
        )
        reader = csv.DictReader(content.splitlines())
        if reader.fieldnames is None:
            raise TelemetryAdapterError("CSV source has no header")
        missing = {
            field
            for field in (
                self.schema.timestamp,
                self.schema.value,
                self.schema.source_id,
            )
            if field not in reader.fieldnames
        }
        if missing:
            raise TelemetryAdapterError(f"CSV schema missing required fields: {sorted(missing)}")
        for row_number, row in enumerate(reader, start=2):
            yield _record(
                row,
                row_number=row_number,
                schema=self.schema,
                time_mapper=self.time_mapper,
                provenance=provenance,
                default_domain=self.default_domain,
                default_metric=self.default_metric,
                default_unit=self.default_unit,
            )

    def read_path(self, path: Path) -> list[TelemetryRecord]:
        with path.open("r", encoding="utf-8", newline="") as stream:
            self.source_uri = self.source_uri or path.as_uri()
            return list(self.iter_records(stream))


class OPSSATSegmentsAdapter:
    """Adapter for the published OPS-SAT/OPSSAT-AD segments.csv schema."""

    def __init__(self, *, time_mapper: TelemetryTimeMapper) -> None:
        self.time_mapper = time_mapper

    def iter_records(
        self, stream: TextIOBase, *, source_uri: str | None = None
    ) -> Iterator[TelemetryRecord]:
        content = stream.read()
        provenance = TelemetryProvenance.from_bytes(
            content.encode("utf-8"),
            source_name="ESA OPS-SAT / OPSSAT-AD segments.csv",
            source_uri=source_uri,
            schema="opssat-ad/segments.csv",
            external=source_uri is not None,
        )
        reader = csv.DictReader(content.splitlines())
        required = {"timestamp", "channel", "value"}
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise TelemetryAdapterError(f"OPS-SAT segments.csv missing fields: {sorted(missing)}")
        for row_number, row in enumerate(reader, start=2):
            channel = row["channel"].strip()
            metric_text = row.get("label", "").strip() or channel
            # Published datasets contain arbitrary channel names. Preserve them as metadata
            # while requiring a known normalized metric only when one is explicitly supplied.
            try:
                metric = _metric(metric_text)
            except TelemetryAdapterError:
                metric = TelemetryMetric.RECEIVED_POWER_DBM
            synthetic = dict(row)
            synthetic["source_id"] = channel or "opssat"
            synthetic["metric"] = metric.value
            synthetic["domain"] = "space"
            synthetic["unit"] = row.get("unit", "unknown") or "unknown"
            synthetic["sequence"] = str(row_number - 2)
            synthetic["record_id"] = f"opssat:{row_number - 1}"
            record = _record(
                synthetic,
                row_number=row_number,
                schema=TelemetrySchema(
                    timestamp="timestamp",
                    value="value",
                    source_id="source_id",
                    metric="metric",
                    domain="domain",
                    unit="unit",
                    sequence="sequence",
                    record_id="record_id",
                ),
                time_mapper=self.time_mapper,
                provenance=provenance,
                default_domain=NetworkDomain.SPACE,
            )
            metadata = record.metadata.copy()
            for key in ("label", "segment", "sampling", "train", "test", "channel"):
                if row.get(key) is not None:
                    metadata[f"opssat_{key}"] = row[key]
            yield record.model_copy(update={"metadata": metadata})

    def read_path(self, path: Path) -> list[TelemetryRecord]:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return list(self.iter_records(stream, source_uri=path.resolve().as_uri()))


class SatNOGSDecodedTelemetryAdapter:
    """Normalize decoded SatNOGS JSON observations while preserving source fields."""

    def __init__(self, *, time_mapper: TelemetryTimeMapper) -> None:
        self.time_mapper = time_mapper

    def records_from_payload(
        self,
        payload: Any,
        *,
        source_uri: str | None = None,
    ) -> list[TelemetryRecord]:
        content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        provenance = TelemetryProvenance.from_bytes(
            content,
            source_name="SatNOGS decoded telemetry",
            source_uri=source_uri,
            schema="satnogs/decoded-json",
            external=source_uri is not None,
        )
        observations = (
            payload
            if isinstance(payload, list)
            else payload.get("results", payload.get("data", []))
        )
        if not isinstance(observations, list):
            raise TelemetryAdapterError("SatNOGS JSON must contain a list or results/data list")
        records: list[TelemetryRecord] = []
        for index, item in enumerate(observations):
            if not isinstance(item, dict):
                raise TelemetryAdapterError(f"SatNOGS observation {index} is not an object")
            timestamp_value = item.get("timestamp", item.get("time"))
            source_id = str(item.get("source_id", item.get("satellite", "satnogs"))).strip()
            metric_value = item.get("metric", item.get("label"))
            value = item.get("value")
            if timestamp_value is None or metric_value is None or value is None:
                raise TelemetryAdapterError(
                    f"SatNOGS observation {index} requires timestamp, metric/label and value"
                )
            if isinstance(timestamp_value, (int, float)):
                timestamp = datetime.fromtimestamp(float(timestamp_value), tz=UTC)
            else:
                timestamp = self.time_mapper.parse_timestamp(str(timestamp_value))
            try:
                metric = _metric(str(metric_value))
            except TelemetryAdapterError as exc:
                raise TelemetryAdapterError(
                    f"SatNOGS observation {index} has unsupported metric {metric_value!r}"
                ) from exc
            domain = _domain(str(item.get("domain", "space")))
            unit = str(item.get("unit", "unknown"))
            sequence = _parse_sequence(str(item["sequence"]) if "sequence" in item else None, index)
            record_id = str(item.get("id", f"satnogs:{index}"))
            metadata = provenance.metadata()
            metadata["source_index"] = str(index)
            metadata["source_timestamp_utc"] = timestamp.astimezone(UTC).isoformat()
            for key, value_item in item.items():
                if key not in {"timestamp", "time", "value", "metric", "label", "unit", "sequence"}:
                    metadata[f"satnogs_{key}"] = str(value_item)
            records.append(
                TelemetryRecord(
                    record_id=record_id,
                    timestamp_s=self.time_mapper.to_simulation_time(timestamp),
                    sequence=sequence,
                    source_id=source_id,
                    domain=domain,
                    metric=metric,
                    value=float(value),
                    unit=unit,
                    quality=_quality(str(item["quality"]) if "quality" in item else None),
                    metadata=metadata,
                )
            )
        return records

    def fetch(self, url: str, *, timeout_s: float = 15.0) -> list[TelemetryRecord]:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout_s) as response:
            content = response.read()
        try:
            payload = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise TelemetryAdapterError("SatNOGS HTTP response is not valid JSON") from exc
        return self.records_from_payload(payload, source_uri=url)


def records_to_json(records: Iterable[TelemetryRecord]) -> str:
    """Serialize normalized telemetry deterministically for fixtures and demos."""
    return json.dumps(
        [record.model_dump(mode="json") for record in records],
        indent=2,
        sort_keys=True,
    )
