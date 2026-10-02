from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sag_network.real_baseline_comparison import RealDataBaselineComparisonRunner


def make_dataset(path: Path) -> None:
    rows = []
    for index in range(60):
        rows.append([index, "fixture-channel", 20.0 - 0.25 * index, 1])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train"])
        writer.writerows(rows)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".manifest.json").write_text(
        json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
    )


def test_real_baseline_comparison_is_deterministic(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    runner = RealDataBaselineComparisonRunner()
    first = runner.run(dataset)
    second = runner.run(dataset)
    assert first == second
    assert first.compared_series_count == 1
    assert len(first.aggregate_metrics) == 3


def test_real_baseline_comparison_requires_provenance(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    dataset.with_suffix(dataset.suffix + ".manifest.json").unlink()
    with pytest.raises(ValueError, match="verified provenance"):
        RealDataBaselineComparisonRunner().run(dataset)


def test_real_baseline_comparison_supports_iso_timestamp(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    with dataset.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train"])
        start = datetime(2022, 6, 1, 23, 42, 54, tzinfo=timezone.utc)
        for index in range(60):
            timestamp = start + timedelta(seconds=index)
            writer.writerow([
                timestamp.isoformat().replace("+00:00", "Z"),
                "fixture-channel",
                20.0 - index * 0.1,
                1,
            ])
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    dataset.with_suffix(dataset.suffix + ".manifest.json").write_text(
        json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
    )
    report = RealDataBaselineComparisonRunner().run(dataset)
    assert report.status == "pass"
