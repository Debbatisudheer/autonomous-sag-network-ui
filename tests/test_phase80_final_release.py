from __future__ import annotations

from pathlib import Path

from sag_network.final_release import (
    FinalReleaseStatus,
    build_checkpoint_matrix,
    build_final_release_report,
)

ROOT = Path(__file__).resolve().parents[1]


def test_phase80_checkpoint_matrix_preserves_skip_boundary() -> None:
    matrix = build_checkpoint_matrix()
    assert any(item.phase == "46" and item.status == "SKIPPED" for item in matrix)
    assert sum(item.status == "LOCKED" for item in matrix) == 25


def test_phase80_final_release_report_is_passable() -> None:
    report = build_final_release_report(ROOT)
    assert report.status is FinalReleaseStatus.PASS
    assert report.version == "2.0.0"
    assert report.phase == "80"
    assert report.network_mutation is False
    assert report.hardware_measurement is False
    assert report.evidence_boundary_clean is True
    assert report.deterministic is True
    assert report.locked_checkpoint_count == 25
    assert report.skipped_checkpoint_count == 1
    assert all(check.status is FinalReleaseStatus.PASS for check in report.checks)


def test_phase80_final_release_report_is_deterministic() -> None:
    first = build_final_release_report(ROOT)
    second = build_final_release_report(ROOT)
    assert first.release_tree_fingerprint == second.release_tree_fingerprint
    assert first.checkpoint_matrix_fingerprint == second.checkpoint_matrix_fingerprint
    assert first.release_fingerprint == second.release_fingerprint
