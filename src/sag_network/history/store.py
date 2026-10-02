from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from sag_network.history.models import (
    HistoricalDatasetConfig,
    HistoricalDatasetManifest,
    HistoricalDatasetStatus,
    HistoricalQuery,
    HistoricalQueryResult,
)
from sag_network.telemetry.models import TelemetryRecord


class HistoricalDatasetError(ValueError):
    """Raised when a historical dataset operation violates its contract."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _record_json(record: TelemetryRecord) -> str:
    return _canonical_json(record.model_dump(mode="json"))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class HistoricalDatasetStore:
    """Partitioned, deterministic JSONL historical telemetry store."""

    def __init__(self, root: Path, *, config: HistoricalDatasetConfig | None = None) -> None:
        self.root = root
        self.config = config or HistoricalDatasetConfig()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, dataset_id: str) -> HistoricalDatasetManifest:
        dataset_dir = self._dataset_dir(dataset_id)
        if dataset_dir.exists():
            raise HistoricalDatasetError(f"dataset already exists: {dataset_id}")
        dataset_dir.mkdir(parents=True)
        manifest = self._build_manifest(dataset_id, HistoricalDatasetStatus.BUILDING)
        self._write_manifest(manifest)
        return manifest

    def append(self, dataset_id: str, records: Iterable[TelemetryRecord]) -> int:
        manifest = self.manifest(dataset_id)
        if manifest.status is HistoricalDatasetStatus.SEALED:
            raise HistoricalDatasetError("sealed datasets are immutable")
        materialized = sorted(records, key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
        if not materialized:
            return 0
        existing_ids = self._record_ids(dataset_id)
        grouped: dict[int, list[TelemetryRecord]] = {}
        accepted = 0
        for record in materialized:
            if record.record_id in existing_ids and not self.config.allow_duplicate_record_ids:
                raise HistoricalDatasetError(f"duplicate record_id: {record.record_id}")
            partition = int(record.timestamp_s // self.config.partition_span_s)
            grouped.setdefault(partition, []).append(record)
            existing_ids.add(record.record_id)
            accepted += 1
        for partition, partition_records in grouped.items():
            path = self._partition_path(dataset_id, partition)
            current = self._read_partition(path) if path.exists() else []
            current.extend(partition_records)
            current.sort(key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
            content = "".join(f"{_record_json(record)}\n" for record in current)
            _atomic_write(path, content)
        self._write_manifest(self._build_manifest(dataset_id, HistoricalDatasetStatus.BUILDING))
        return accepted

    def seal(self, dataset_id: str) -> HistoricalDatasetManifest:
        manifest = self._build_manifest(dataset_id, HistoricalDatasetStatus.SEALED)
        self._write_manifest(manifest)
        return manifest

    def manifest(self, dataset_id: str) -> HistoricalDatasetManifest:
        path = self._manifest_path(dataset_id)
        if not path.exists():
            raise HistoricalDatasetError(f"unknown dataset: {dataset_id}")
        return HistoricalDatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def query(self, dataset_id: str, query: HistoricalQuery | None = None) -> HistoricalQueryResult:
        manifest = self.manifest(dataset_id)
        query = query or HistoricalQuery()
        query.validate_window()
        records: list[TelemetryRecord] = []
        for path in self._partition_paths(dataset_id):
            partition_records = self._read_partition(path)
            for record in partition_records:
                if not self._matches(record, query):
                    continue
                records.append(record)
        records.sort(key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
        if query.limit is not None:
            records = records[: query.limit]
        return HistoricalQueryResult(
            dataset_id=dataset_id,
            records=records,
            dataset_fingerprint=manifest.dataset_fingerprint,
        )

    def list_datasets(self) -> list[str]:
        return sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_dir() and (path / "manifest.json").exists()
        )

    def _matches(self, record: TelemetryRecord, query: HistoricalQuery) -> bool:
        if query.start_time_s is not None and record.timestamp_s < query.start_time_s:
            return False
        if query.end_time_s is not None and record.timestamp_s > query.end_time_s:
            return False
        if query.source_ids and record.source_id not in query.source_ids:
            return False
        if query.domains and record.domain not in query.domains:
            return False
        if query.metrics and record.metric.value not in query.metrics:
            return False
        return not query.qualities or record.quality in query.qualities

    def _build_manifest(
        self, dataset_id: str, status: HistoricalDatasetStatus
    ) -> HistoricalDatasetManifest:
        records: list[TelemetryRecord] = []
        partition_fingerprints: list[str] = []
        source_fingerprints: set[str] = set()
        for path in self._partition_paths(dataset_id):
            content = path.read_bytes()
            partition_fingerprints.append(_sha256_bytes(content))
            for record in self._read_partition(path):
                records.append(record)
                fingerprint = record.metadata.get("provenance_sha256")
                if fingerprint:
                    source_fingerprints.add(fingerprint)
        records.sort(key=lambda item: (item.timestamp_s, item.sequence, item.record_id))
        payload = {
            "dataset_id": dataset_id,
            "schema_version": "1",
            "record_count": len(records),
            "partition_fingerprints": sorted(partition_fingerprints),
            "source_fingerprints": sorted(source_fingerprints),
        }
        fingerprint = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
        return HistoricalDatasetManifest(
            dataset_id=dataset_id,
            status=status,
            record_count=len(records),
            partition_count=len(partition_fingerprints),
            min_timestamp_s=records[0].timestamp_s if records else None,
            max_timestamp_s=records[-1].timestamp_s if records else None,
            source_count=len(source_fingerprints),
            source_fingerprints=tuple(sorted(source_fingerprints)),
            partition_fingerprints=tuple(sorted(partition_fingerprints)),
            dataset_fingerprint=fingerprint,
        )

    def _write_manifest(self, manifest: HistoricalDatasetManifest) -> None:
        _atomic_write(self._manifest_path(manifest.dataset_id), manifest.model_dump_json(indent=2))

    def _record_ids(self, dataset_id: str) -> set[str]:
        return {record.record_id for path in self._partition_paths(dataset_id) for record in self._read_partition(path)}

    def _read_partition(self, path: Path) -> list[TelemetryRecord]:
        if not path.exists():
            return []
        return [TelemetryRecord.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def _partition_paths(self, dataset_id: str) -> list[Path]:
        partition_dir = self._dataset_dir(dataset_id) / "partitions"
        if not partition_dir.exists():
            return []
        return sorted(partition_dir.glob("part-*.jsonl"))

    def _partition_path(self, dataset_id: str, partition: int) -> Path:
        return self._dataset_dir(dataset_id) / "partitions" / f"part-{partition:012d}.jsonl"

    def _dataset_dir(self, dataset_id: str) -> Path:
        if not dataset_id or "/" in dataset_id or "\\" in dataset_id or dataset_id in {".", ".."}:
            raise HistoricalDatasetError("dataset_id must be a simple non-empty identifier")
        return self.root / dataset_id

    def _manifest_path(self, dataset_id: str) -> Path:
        return self._dataset_dir(dataset_id) / "manifest.json"
