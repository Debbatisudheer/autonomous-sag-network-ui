from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sag_network.real_uncertainty_calibration import (
    RealDataUncertaintyCalibrationRunner,
    RealUncertaintyCalibrationConfig,
    RealUncertaintyEvidence,
)


def make_dataset(path: Path) -> None:
    rows = []
    for index in range(120):
        rows.append([index, "fixture-channel", 20.0 - 0.25 * index, 1])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train"])
        writer.writerows(rows)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".manifest.json").write_text(
        json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
    )


def test_real_uncertainty_calibration_is_deterministic(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    runner = RealDataUncertaintyCalibrationRunner()
    config = RealUncertaintyCalibrationConfig(minimum_calibration_samples=10)
    first = runner.run(dataset, config=config)
    second = runner.run(dataset, config=config)
    assert first == second
    assert first.calibrated_series_count == 1
    assert first.aggregate_test_sample_count > 0
    assert 0.0 <= first.aggregate_empirical_coverage <= 1.0
    assert first.series_results[0].interval_model_fingerprint != ""
    assert first.series_results[0].coverage_status in {"below_target", "meets_or_exceeds_target"}


def test_real_uncertainty_requires_provenance(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    dataset.with_suffix(dataset.suffix + ".manifest.json").unlink()
    with pytest.raises(ValueError, match="verified provenance"):
        RealDataUncertaintyCalibrationRunner().run(dataset)


def test_real_uncertainty_supports_iso_timestamp(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    with dataset.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train"])
        start = datetime(2022, 6, 1, 23, 42, 54, tzinfo=timezone.utc)
        for index in range(120):
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
    report = RealDataUncertaintyCalibrationRunner().run(
        dataset,
        config=RealUncertaintyCalibrationConfig(minimum_calibration_samples=10),
        evidence_class=RealUncertaintyEvidence.PUBLIC_DATA,
    )
    assert report.status == "pass"
    assert report.calibration_method == "split_conformal_absolute_residual"


def test_real_uncertainty_allows_synthetic_fixture_without_provenance(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    make_dataset(dataset)
    dataset.with_suffix(dataset.suffix + ".manifest.json").unlink()
    report = RealDataUncertaintyCalibrationRunner().run(
        dataset,
        config=RealUncertaintyCalibrationConfig(minimum_calibration_samples=10),
        evidence_class=RealUncertaintyEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.evidence_class is RealUncertaintyEvidence.SYNTHETIC_FIXTURE
