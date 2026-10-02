from __future__ import annotations

from pydantic import BaseModel, Field


class FileFingerprint(BaseModel):
    """Content fingerprint for one reproducibility-relevant file."""

    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)


class ReproducibilityManifest(BaseModel):
    """Deterministic manifest describing a research run and its source inputs."""

    package_id: str = Field(min_length=1, max_length=128)
    phase: str = Field(min_length=1, max_length=32)
    source_files: tuple[FileFingerprint, ...] = Field(min_length=1)
    commands: tuple[str, ...] = Field(min_length=1)
    runtime: dict[str, str]
    evidence_class: str = Field(min_length=1)
    notes: tuple[str, ...]
    manifest_fingerprint: str = Field(min_length=64, max_length=64)


class ReproducibilityCheck(BaseModel):
    """Result of comparing a manifest against supplied files."""

    package_id: str
    checked_files: int = Field(ge=0)
    matched_files: int = Field(ge=0)
    missing_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    reproducible: bool
    verification_fingerprint: str = Field(min_length=64, max_length=64)
