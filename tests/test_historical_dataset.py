from __future__ import annotations

from pathlib import Path

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.history import (
    HistoricalDatasetConfig,
    HistoricalDatasetError,
    HistoricalDatasetStatus,
    HistoricalDatasetStore,
    HistoricalQuery,
)
from sag_network.telemetry import TelemetryMetric, TelemetryRecord


def record(
    record_id: str,
    timestamp_s: float,
    sequence: int,
    *,
    source_id: str = "sat-1",
    metric: TelemetryMetric = TelemetryMetric.SINR_DB,
) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=sequence,
        source_id=source_id,
        domain=NetworkDomain.SPACE,
        metric=metric,
        value=float(sequence),
        unit="dB",
        metadata={"provenance_sha256": f"{'a' * 63}{sequence % 10}"},
    )


def test_create_append_query_and_seal(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path, config=HistoricalDatasetConfig(partition_span_s=10))
    created = store.create("dataset-a")
    assert created.status is HistoricalDatasetStatus.BUILDING
    assert store.append("dataset-a", [record("r2", 12, 2), record("r1", 2, 1)]) == 2

    result = store.query("dataset-a", HistoricalQuery(start_time_s=0, end_time_s=15))
    assert [item.record_id for item in result.records] == ["r1", "r2"]
    assert result.count == 2

    sealed = store.seal("dataset-a")
    assert sealed.status is HistoricalDatasetStatus.SEALED
    assert sealed.record_count == 2
    assert sealed.partition_count == 2
    assert len(sealed.dataset_fingerprint) == 64


def test_sealed_dataset_is_immutable(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    store.create("dataset")
    store.append("dataset", [record("r1", 1, 1)])
    store.seal("dataset")
    with pytest.raises(HistoricalDatasetError, match="immutable"):
        store.append("dataset", [record("r2", 2, 2)])


def test_duplicate_record_id_is_rejected(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    store.create("dataset")
    store.append("dataset", [record("r1", 1, 1)])
    with pytest.raises(HistoricalDatasetError, match="duplicate"):
        store.append("dataset", [record("r1", 2, 2)])


def test_query_filters_source_metric_and_window(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    store.create("dataset")
    store.append(
        "dataset",
        [
            record("a", 1, 1, source_id="sat-1", metric=TelemetryMetric.SINR_DB),
            record("b", 2, 2, source_id="sat-2", metric=TelemetryMetric.LATENCY_MS),
            record("c", 3, 3, source_id="sat-1", metric=TelemetryMetric.SINR_DB),
        ],
    )
    result = store.query(
        "dataset",
        HistoricalQuery(
            start_time_s=1.5,
            end_time_s=3,
            source_ids=("sat-1",),
            metrics=(TelemetryMetric.SINR_DB.value,),
        ),
    )
    assert [item.record_id for item in result.records] == ["c"]


def test_query_limit_is_deterministic(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    store.create("dataset")
    store.append("dataset", [record(f"r{i}", float(i), i) for i in range(5)])
    result = store.query("dataset", HistoricalQuery(limit=3))
    assert [item.record_id for item in result.records] == ["r0", "r1", "r2"]


def test_dataset_fingerprint_is_stable_for_same_content(tmp_path: Path) -> None:
    records = [record("r1", 1, 1), record("r2", 2, 2)]
    first = HistoricalDatasetStore(tmp_path / "a")
    second = HistoricalDatasetStore(tmp_path / "b")
    first.create("dataset")
    second.create("dataset")
    first.append("dataset", records)
    second.append("dataset", records)
    assert first.manifest("dataset").dataset_fingerprint == second.manifest("dataset").dataset_fingerprint


def test_dataset_catalog_is_sorted(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    store.create("zeta")
    store.create("alpha")
    assert store.list_datasets() == ["alpha", "zeta"]


def test_invalid_query_window_is_rejected(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    store.create("dataset")
    with pytest.raises(ValueError, match="end_time_s"):
        store.query("dataset", HistoricalQuery(start_time_s=3, end_time_s=2))


def test_unknown_dataset_is_rejected(tmp_path: Path) -> None:
    store = HistoricalDatasetStore(tmp_path)
    with pytest.raises(HistoricalDatasetError, match="unknown dataset"):
        store.manifest("missing")
