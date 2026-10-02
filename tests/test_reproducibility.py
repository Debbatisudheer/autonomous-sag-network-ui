from __future__ import annotations

from pathlib import Path

import pytest

from sag_network.reproducibility import build_manifest, verify_manifest


def test_manifest_is_deterministic_and_excludes_caches(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("print('ok')\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "src.cpython-311.pyc").write_bytes(b"cache")

    first = build_manifest(
        tmp_path,
        package_id="p",
        phase="52",
        commands=("pytest -q",),
        runtime={"python": "3.11"},
        evidence_class="synthetic offline reproducibility fixture",
    )
    second = build_manifest(
        tmp_path,
        package_id="p",
        phase="52",
        commands=("pytest -q",),
        runtime={"python": "3.11"},
        evidence_class="synthetic offline reproducibility fixture",
    )
    assert first == second
    assert [item.path for item in first.source_files] == ["src.py"]


def test_manifest_verifies_unchanged_tree(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    manifest = build_manifest(
        tmp_path,
        package_id="p",
        phase="52",
        commands=("pytest -q",),
        runtime={"python": "3.11"},
        evidence_class="fixture",
    )
    check = verify_manifest(tmp_path, manifest)
    assert check.reproducible is True
    assert check.checked_files == 1
    assert check.matched_files == 1


def test_manifest_detects_changed_and_extra_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    manifest = build_manifest(
        tmp_path,
        package_id="p",
        phase="52",
        commands=("pytest -q",),
        runtime={"python": "3.11"},
        evidence_class="fixture",
    )
    (tmp_path / "a.txt").write_text("beta", encoding="utf-8")
    (tmp_path / "extra.txt").write_text("extra", encoding="utf-8")
    check = verify_manifest(tmp_path, manifest)
    assert check.reproducible is False
    assert check.changed_files == ("a.txt", "extra.txt")


def test_empty_manifest_inputs_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one source file"):
        build_manifest(
            tmp_path,
            package_id="p",
            phase="52",
            commands=("pytest -q",),
            runtime={},
            evidence_class="fixture",
        )
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    with pytest.raises(ValueError, match="at least one command"):
        build_manifest(
            tmp_path,
            package_id="p",
            phase="52",
            commands=(),
            runtime={},
            evidence_class="fixture",
        )
