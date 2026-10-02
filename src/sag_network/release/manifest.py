from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, Field

from sag_network.reproducibility.manifest import collect_files

_RELEASE_MANIFEST_NAME = "release_manifest.json"

_EXCLUDED_RELEASE_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}

_EXCLUDED_RELEASE_SUFFIXES = {".pyc", ".pyo"}


class ReleaseManifest(BaseModel):
    release_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    phase: str = "55"
    source_file_count: int = Field(ge=1)
    test_file_count: int = Field(ge=1)
    source_tree_fingerprint: str = Field(min_length=64, max_length=64)
    phase54_benchmark_fingerprint: str = Field(min_length=64, max_length=64)
    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    evidence_class: str = Field(min_length=1)
    network_mutation: bool
    excluded_artifacts: tuple[str, ...]
    deterministic: bool
    release_fingerprint: str = Field(min_length=64, max_length=64)


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _release_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(part in _EXCLUDED_RELEASE_PARTS for part in relative.parts):
            continue

        if path.suffix in _EXCLUDED_RELEASE_SUFFIXES:
            continue

        if relative.as_posix() == _RELEASE_MANIFEST_NAME:
            continue

        files.append(path)

    return tuple(
        sorted(
            files,
            key=lambda item: item.relative_to(root).as_posix(),
        )
    )


def build_release_manifest(
    root: Path,
    *,
    version: str,
    phase54_benchmark_fingerprint: str,
    evidence_class: str,
    network_mutation: bool,
    excluded_artifacts: Iterable[str],
    runtime: Mapping[str, str] | None = None,
) -> ReleaseManifest:
    files = _release_files(root)

    if not files:
        raise ValueError("final release requires at least one eligible file")

    fingerprints = collect_files(root, paths=files)

    payload = [
        item.model_dump(mode="json")
        for item in fingerprints
    ]

    source_tree_fingerprint = _fingerprint(payload)

    source_file_count = sum(
        item.path.startswith("src/") and item.path.endswith(".py")
        for item in fingerprints
    )

    test_file_count = sum(
        item.path.startswith("tests/") and item.path.endswith(".py")
        for item in fingerprints
    )

    if source_file_count == 0 or test_file_count == 0:
        raise ValueError(
            "final release must contain source and test files"
        )

    runtime_values = dict(runtime or {})

    python_version = runtime_values.get(
        "python_version",
        platform.python_version(),
    )

    platform_name = runtime_values.get(
        "platform",
        platform.platform(),
    )

    excluded = tuple(sorted(excluded_artifacts))

    release_payload = {
        "release_id": "autonomous-sag-network-1.0.0",
        "version": version,
        "phase": "55",
        "source_file_count": source_file_count,
        "test_file_count": test_file_count,
        "source_tree_fingerprint": source_tree_fingerprint,
        "phase54_benchmark_fingerprint": phase54_benchmark_fingerprint,
        "python_version": python_version,
        "platform": platform_name,
        "evidence_class": evidence_class,
        "network_mutation": network_mutation,
        "excluded_artifacts": excluded,
        "deterministic": True,
    }

    release_fingerprint = _fingerprint(release_payload)

    return ReleaseManifest(
        release_id="autonomous-sag-network-1.0.0",
        version=version,
        phase="55",
        source_file_count=source_file_count,
        test_file_count=test_file_count,
        source_tree_fingerprint=source_tree_fingerprint,
        phase54_benchmark_fingerprint=phase54_benchmark_fingerprint,
        python_version=python_version,
        platform=platform_name,
        evidence_class=evidence_class,
        network_mutation=network_mutation,
        excluded_artifacts=excluded,
        deterministic=True,
        release_fingerprint=release_fingerprint,
    )


def current_runtime() -> dict[str, str]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }