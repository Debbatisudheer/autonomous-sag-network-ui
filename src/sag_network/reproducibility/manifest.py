from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from sag_network.reproducibility.models import (
    FileFingerprint,
    ReproducibilityCheck,
    ReproducibilityManifest,
)

_EXCLUDED_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _eligible(path: Path) -> bool:
    return not any(part in _EXCLUDED_PARTS for part in path.parts) and path.suffix not in _EXCLUDED_SUFFIXES


def collect_files(root: Path, paths: Iterable[Path] | None = None) -> tuple[FileFingerprint, ...]:
    """Collect deterministic content fingerprints for a research tree."""
    candidates = list(paths) if paths is not None else list(root.rglob("*"))
    files = sorted(
        (path for path in candidates if path.is_file() and _eligible(path)),
        key=lambda item: item.as_posix(),
    )
    return tuple(
        FileFingerprint(
            path=path.relative_to(root).as_posix(),
            sha256=_file_sha256(path),
            size_bytes=path.stat().st_size,
        )
        for path in files
    )


def build_manifest(
    root: Path,
    *,
    package_id: str,
    phase: str,
    commands: Iterable[str],
    runtime: Mapping[str, str],
    evidence_class: str,
    notes: Iterable[str] = (),
    paths: Iterable[Path] | None = None,
) -> ReproducibilityManifest:
    files = collect_files(root, paths)
    if not files:
        raise ValueError("reproducibility manifest requires at least one source file")
    command_tuple = tuple(commands)
    if not command_tuple:
        raise ValueError("reproducibility manifest requires at least one command")
    payload = {
        "package_id": package_id,
        "phase": phase,
        "source_files": [item.model_dump(mode="json") for item in files],
        "commands": command_tuple,
        "runtime": dict(runtime),
        "evidence_class": evidence_class,
        "notes": tuple(notes),
    }
    return ReproducibilityManifest(
        package_id=package_id,
        phase=phase,
        source_files=files,
        commands=command_tuple,
        runtime=dict(runtime),
        evidence_class=evidence_class,
        notes=tuple(notes),
        manifest_fingerprint=_fingerprint(payload),
    )


def verify_manifest(root: Path, manifest: ReproducibilityManifest) -> ReproducibilityCheck:
    expected = {item.path: item for item in manifest.source_files}
    actual = {item.path: item for item in collect_files(root)}
    missing = tuple(sorted(set(expected) - set(actual)))
    changed = tuple(
        sorted(path for path in set(expected) & set(actual) if expected[path] != actual[path])
    )
    extra = tuple(sorted(set(actual) - set(expected)))
    payload = {
        "package_id": manifest.package_id,
        "missing_files": missing,
        "changed_files": changed,
        "extra_files": extra,
    }
    return ReproducibilityCheck(
        package_id=manifest.package_id,
        checked_files=len(expected),
        matched_files=len(expected) - len(missing) - len(changed),
        missing_files=missing,
        changed_files=changed + extra,
        reproducible=not missing and not changed and not extra,
        verification_fingerprint=_fingerprint(payload),
    )
