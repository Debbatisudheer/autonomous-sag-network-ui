from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sag_network.real_domain_shift import (
    DomainShiftConfig,
    DomainShiftEvidence,
    RealDomainShiftRunner,
)
from sag_network.real_domain_shift.runner import (
    _empirical_cdf_distance,
    _parse_timestamp,
    _psi,
)


def write_dataset(path: Path, values: list[float]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        for index, value in enumerate(values):
            writer.writerow([index, "channel-a", value, 1, 0, "normal"])


def test_numeric_and_iso_timestamps() -> None:
    assert _parse_timestamp("123.5") == 123.5
    assert _parse_timestamp("2022-06-01T23:42:54.000Z") == pytest.approx(
        1654126974.0
    )


def test_identical_distributions_have_no_shift(tmp_path: Path) -> None:
    values = [float(index % 24) for index in range(120)]
    path = tmp_path / "phase65-identical.csv"
    write_dataset(path, values)
    report = RealDomainShiftRunner().run(
        path,
        config=DomainShiftConfig(
            minimum_comparison_samples=10,
            max_rows_per_series=120,
        ),
        evidence_class=DomainShiftEvidence.SYNTHETIC_FIXTURE,
    )
    result = report.series_results[0]
    assert result.shift_detected is False
    assert result.shift_score < 0.5


def test_mean_shift_is_detected(tmp_path: Path) -> None:
    values = [10.0] * 80 + [25.0] * 40
    path = tmp_path / "phase65-shift.csv"
    write_dataset(path, values)
    report = RealDomainShiftRunner().run(
        path,
        config=DomainShiftConfig(
            minimum_comparison_samples=10,
            max_rows_per_series=120,
        ),
        evidence_class=DomainShiftEvidence.SYNTHETIC_FIXTURE,
    )
    result = report.series_results[0]
    assert result.shift_detected is True
    assert "standardized_mean_shift" in result.detection_reasons
    assert report.shifted_series_count == 1


def test_detection_is_deterministic(tmp_path: Path) -> None:
    values = [10.0] * 80 + [25.0] * 40
    path = tmp_path / "phase65-deterministic.csv"
    write_dataset(path, values)
    runner = RealDomainShiftRunner()
    first = runner.run(
        path,
        config=DomainShiftConfig(
            minimum_comparison_samples=10,
            max_rows_per_series=120,
        ),
        evidence_class=DomainShiftEvidence.SYNTHETIC_FIXTURE,
    )
    second = runner.run(
        path,
        config=DomainShiftConfig(
            minimum_comparison_samples=10,
            max_rows_per_series=120,
        ),
        evidence_class=DomainShiftEvidence.SYNTHETIC_FIXTURE,
    )
    assert first == second


def test_distribution_helpers() -> None:
    reference = [0.0, 0.0, 1.0, 1.0]
    comparison = [0.0, 0.0, 1.0, 1.0]
    assert _psi(reference, comparison, 4) == pytest.approx(0.0)
    assert _empirical_cdf_distance(reference, comparison) == pytest.approx(0.0)


def test_public_data_requires_manifest(tmp_path: Path) -> None:
    path = tmp_path / "segments.csv"
    write_dataset(path, [1.0] * 100)
    with pytest.raises(ValueError, match="verified provenance manifest"):
        RealDomainShiftRunner().run(path)
