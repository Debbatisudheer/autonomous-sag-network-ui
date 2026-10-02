from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sag_network.real_failure_intelligence import (
    RealFailureEvidence,
    RealFailureIntelligenceConfig,
    RealFailureIntelligenceRunner,
)


def make_dataset(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        for index in range(140):
            anomaly = int(index >= 112)
            value = 20.0 + 0.05 * index + (15.0 if anomaly else 0.0)
            writer.writerow([index, "fixture-channel", value, 1, anomaly, "anomaly" if anomaly else "normal"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".manifest.json").write_text(
        json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
    )


def test_real_failure_intelligence_is_deterministic(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    config = RealFailureIntelligenceConfig(minimum_calibration_samples=10)
    runner = RealFailureIntelligenceRunner()
    first = runner.run(dataset, config=config)
    second = runner.run(dataset, config=config)
    assert first == second
    assert first.analyzed_series_count == 1
    assert first.flagged_risk_count > 0
    assert first.intelligence_fingerprint


def test_real_failure_intelligence_uses_verified_provenance(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    dataset.with_suffix(dataset.suffix + ".manifest.json").unlink()
    with pytest.raises(ValueError, match="verified provenance"):
        RealFailureIntelligenceRunner().run(dataset)


def test_real_failure_intelligence_supports_iso_timestamp(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    with dataset.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        start = datetime(2022, 6, 1, 23, 42, 54, tzinfo=timezone.utc)
        for index in range(140):
            timestamp = start + timedelta(seconds=index)
            writer.writerow([
                timestamp.isoformat().replace("+00:00", "Z"),
                "fixture-channel",
                20.0 + 0.05 * index,
                1,
                0,
                "normal",
            ])
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    dataset.with_suffix(dataset.suffix + ".manifest.json").write_text(
        json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
    )
    report = RealFailureIntelligenceRunner().run(
        dataset,
        config=RealFailureIntelligenceConfig(minimum_calibration_samples=10),
        evidence_class=RealFailureEvidence.PUBLIC_DATA,
    )
    assert report.status == "pass"


def test_anomaly_labels_are_not_used_without_test_alignment(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    with dataset.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        for index in range(140):
            writer.writerow([index, "fixture-channel", 20.0, 1, 1 if index < 20 else 0, "anomaly" if index < 20 else "normal"])
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    dataset.with_suffix(dataset.suffix + ".manifest.json").write_text(
        json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
    )
    report = RealFailureIntelligenceRunner().run(
        dataset,
        config=RealFailureIntelligenceConfig(minimum_calibration_samples=10),
    )
    assert report.observed_anomaly_count == 0
