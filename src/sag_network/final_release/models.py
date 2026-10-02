from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FinalReleaseStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ReleaseCheck(BaseModel):
    check_id: str = Field(min_length=1)
    status: FinalReleaseStatus
    observed: str
    expected: str
    detail: str
    fingerprint: str = Field(min_length=64, max_length=64)


class ReleaseCheckpoint(BaseModel):
    phase: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    evidence_scope: str = Field(min_length=1)
    physical_deployment_claim: bool = False


class SAGV2ReleaseReport(BaseModel):
    release_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    phase: str = "80"
    status: FinalReleaseStatus
    checkpoints: list[ReleaseCheckpoint]
    checks: list[ReleaseCheck]
    locked_checkpoint_count: int = Field(ge=0)
    skipped_checkpoint_count: int = Field(ge=0)
    source_file_count: int = Field(ge=1)
    test_file_count: int = Field(ge=1)
    release_tree_fingerprint: str = Field(min_length=64, max_length=64)
    checkpoint_matrix_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_boundary_clean: bool
    network_mutation: bool
    hardware_measurement: bool
    deterministic: bool
    release_fingerprint: str = Field(min_length=64, max_length=64)


__all__ = [
    "FinalReleaseStatus",
    "ReleaseCheck",
    "ReleaseCheckpoint",
    "SAGV2ReleaseReport",
]
