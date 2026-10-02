from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class DatasetQualityError(ValueError):
    """Raised when a real-data quality report cannot be produced."""


@dataclass(frozen=True)
class DatasetQualityReport:
    dataset_name: str
    path: str
    row_count: int
    column_count: int
    columns: tuple[str, ...]
    duplicate_row_count: int
    empty_row_count: int
    null_counts: dict[str, int]
    numeric_columns: tuple[str, ...]
    timestamp_columns: tuple[str, ...]
    label_columns: tuple[str, ...]
    split_columns: tuple[str, ...]
    invalid_numeric_counts: dict[str, int]
    distinct_counts: dict[str, int]
    anomaly_value_counts: dict[str, dict[str, int]]
    source_sha256: str
    quality_fingerprint: str
    provenance_manifest: str | None
    provenance_source_uri: str | None
    provenance_source_page: str | None
    provenance_md5: str | None
    provenance_verified: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _looks_like_timestamp(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("timestamp", "datetime", "date", "time", "utc"))


def _looks_like_label(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("label", "anomaly", "class", "target"))


def _looks_like_split(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("train", "test", "split", "partition"))


def _is_number(value: str) -> bool:
    if not value.strip():
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


def _parse_timestamp(value: str) -> bool:
    if not value.strip():
        return False
    candidate = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return False


def profile_csv(path: Path) -> DatasetQualityReport:
    if not path.is_file():
        raise DatasetQualityError(f"dataset does not exist: {path}")

    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    provenance_manifest = manifest_path.as_posix() if manifest_path.is_file() else None
    provenance_source_uri: str | None = None
    provenance_source_page: str | None = None
    provenance_md5: str | None = None
    provenance_verified = False

    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DatasetQualityError("invalid provenance manifest") from exc

        if manifest.get("sha256") != source_sha256:
            raise DatasetQualityError(
                "provenance manifest SHA-256 does not match the dataset"
            )

        provenance_source_uri = manifest.get("source_uri")
        provenance_source_page = manifest.get("source_page")
        provenance_md5 = manifest.get("md5")
        provenance_verified = manifest.get("verified") is True

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise DatasetQualityError("CSV has no header")

        columns = tuple(reader.fieldnames)
        if any(not column.strip() for column in columns):
            raise DatasetQualityError("CSV contains an empty column name")
        if len(set(columns)) != len(columns):
            raise DatasetQualityError("CSV contains duplicate column names")

        null_counts = Counter({column: 0 for column in columns})
        distinct_values: dict[str, set[str]] = {column: set() for column in columns}
        invalid_numeric_counts: Counter[str] = Counter()
        anomaly_values: dict[str, Counter[str]] = {}
        numeric_candidates: set[str] = set(columns)
        timestamp_columns = tuple(column for column in columns if _looks_like_timestamp(column))
        label_columns = tuple(column for column in columns if _looks_like_label(column))
        split_columns = tuple(column for column in columns if _looks_like_split(column))

        row_count = 0
        empty_row_count = 0
        duplicate_row_count = 0
        seen_rows: set[str] = set()

        for row in reader:
            row_count += 1
            normalized = tuple((row.get(column) or "").strip() for column in columns)
            row_key = _fingerprint(normalized)
            if row_key in seen_rows:
                duplicate_row_count += 1
            seen_rows.add(row_key)

            if all(not value for value in normalized):
                empty_row_count += 1

            for column, value in zip(columns, normalized, strict=True):
                if not value:
                    null_counts[column] += 1
                    continue
                distinct_values[column].add(value)
                if column in numeric_candidates and not _is_number(value):
                    numeric_candidates.discard(column)
                    invalid_numeric_counts[column] += 1

                if column in timestamp_columns and not _parse_timestamp(value):
                    invalid_numeric_counts[f"{column}:timestamp"] += 1

                if column in label_columns:
                    anomaly_values.setdefault(column, Counter())[value] += 1

        numeric_columns = tuple(sorted(numeric_candidates))
        distinct_counts = {column: len(values) for column, values in distinct_values.items()}
        anomaly_value_counts = {
            column: dict(sorted(counter.items()))
            for column, counter in sorted(anomaly_values.items())
        }

    quality_payload: dict[str, Any] = {
        "dataset_name": path.name,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "duplicate_row_count": duplicate_row_count,
        "empty_row_count": empty_row_count,
        "null_counts": dict(sorted(null_counts.items())),
        "numeric_columns": numeric_columns,
        "timestamp_columns": timestamp_columns,
        "label_columns": label_columns,
        "split_columns": split_columns,
        "invalid_numeric_counts": dict(sorted(invalid_numeric_counts.items())),
        "distinct_counts": dict(sorted(distinct_counts.items())),
        "anomaly_value_counts": anomaly_value_counts,
        "source_sha256": source_sha256,
        "provenance_manifest": provenance_manifest,
        "provenance_source_uri": provenance_source_uri,
        "provenance_source_page": provenance_source_page,
        "provenance_md5": provenance_md5,
        "provenance_verified": provenance_verified,
    }

    return DatasetQualityReport(
        dataset_name=path.name,
        path=path.as_posix(),
        row_count=row_count,
        column_count=len(columns),
        columns=columns,
        duplicate_row_count=duplicate_row_count,
        empty_row_count=empty_row_count,
        null_counts=dict(sorted(null_counts.items())),
        numeric_columns=numeric_columns,
        timestamp_columns=timestamp_columns,
        label_columns=label_columns,
        split_columns=split_columns,
        invalid_numeric_counts=dict(sorted(invalid_numeric_counts.items())),
        distinct_counts=dict(sorted(distinct_counts.items())),
        anomaly_value_counts=anomaly_value_counts,
        source_sha256=source_sha256,
        quality_fingerprint=_fingerprint(quality_payload),
        provenance_manifest=provenance_manifest,
        provenance_source_uri=provenance_source_uri,
        provenance_source_page=provenance_source_page,
        provenance_md5=provenance_md5,
        provenance_verified=provenance_verified,
    )
