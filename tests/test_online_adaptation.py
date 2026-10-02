from __future__ import annotations

import csv
from pathlib import Path

import pytest

from sag_network.online_adaptation import (
    OnlineAdaptationConfig,
    OnlineAdaptationEvidence,
    RealOnlineModelAdaptationRunner,
)
from sag_network.online_adaptation.runner import _parse_timestamp, _shift_score


def write_dataset(path: Path, values: list[float]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        for index, value in enumerate(values):
            writer.writerow([index, "channel-a", value, 1, 0, "normal"])


def test_numeric_and_iso_timestamps() -> None:
    assert _parse_timestamp("123.5") == 123.5
    assert _parse_timestamp("2022-06-01T23:42:54.000Z") == pytest.approx(1654126974.0)


def test_shift_score_is_zero_for_identical_values() -> None:
    values = [float(index % 5) for index in range(100)]
    reference_mean = sum(values) / len(values)
    reference_std = (
        sum((value - reference_mean) ** 2 for value in values) / len(values)
    ) ** 0.5
    assert _shift_score(reference_mean, reference_std, values[-50:]) == pytest.approx(0.0)


def test_online_adaptation_runs_and_updates(tmp_path: Path) -> None:
    values = [10.0 + (index % 5) * 0.1 for index in range(90)]
    values.extend(25.0 + (index % 5) * 0.1 for index in range(50))
    path = tmp_path / "phase66.csv"
    write_dataset(path, values)
    report = RealOnlineModelAdaptationRunner().run(
        path,
        config=OnlineAdaptationConfig(
            minimum_samples=20,
            minimum_adaptation_samples=10,
            adaptation_window=30,
            shift_window=20,
            update_interval=10,
            max_rows_per_series=140,
        ),
        evidence_class=OnlineAdaptationEvidence.SYNTHETIC_FIXTURE,
    )
    result = report.series_results[0]
    assert result.total_update_count > 0
    assert result.stream_samples > 0
    assert report.network_mutation is False


def test_online_adaptation_is_deterministic(tmp_path: Path) -> None:
    values = [10.0 + (index % 3) * 0.2 for index in range(120)]
    path = tmp_path / "phase66-deterministic.csv"
    write_dataset(path, values)
    runner = RealOnlineModelAdaptationRunner()
    config = OnlineAdaptationConfig(
        minimum_samples=20,
        minimum_adaptation_samples=10,
        adaptation_window=30,
        shift_window=20,
        update_interval=10,
        max_rows_per_series=120,
    )
    first = runner.run(
        path,
        config=config,
        evidence_class=OnlineAdaptationEvidence.SYNTHETIC_FIXTURE,
    )
    second = runner.run(
        path,
        config=config,
        evidence_class=OnlineAdaptationEvidence.SYNTHETIC_FIXTURE,
    )
    assert first == second
