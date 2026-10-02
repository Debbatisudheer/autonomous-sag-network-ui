from __future__ import annotations

from pathlib import Path

from sag_network.data_quality import profile_csv


def _write_fixture(path: Path) -> None:
    path.write_text(
        "timestamp,value,anomaly_label,split\n"
        "2024-01-01T00:00:00Z,1.0,normal,train\n"
        "2024-01-01T00:00:01Z,2.0,anomaly,test\n"
        "2024-01-01T00:00:01Z,2.0,anomaly,test\n",
        encoding="utf-8",
    )


def test_profile_reports_real_data_quality_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    _write_fixture(dataset)

    report = profile_csv(dataset)

    assert report.row_count == 3
    assert report.column_count == 4
    assert report.duplicate_row_count == 1
    assert report.empty_row_count == 0
    assert report.numeric_columns == ("value",)
    assert report.timestamp_columns == ("timestamp",)
    assert report.label_columns == ("anomaly_label",)
    assert report.split_columns == ("split",)
    assert report.source_sha256
    assert report.quality_fingerprint
    assert report.provenance_verified is False


def test_profile_is_deterministic(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    _write_fixture(dataset)

    first = profile_csv(dataset)
    second = profile_csv(dataset)

    assert first == second
