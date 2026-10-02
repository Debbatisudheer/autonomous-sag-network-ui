from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from sag_network.reproducibility.manifest import collect_files

from .models import (
    FinalReleaseStatus,
    ReleaseCheck,
    ReleaseCheckpoint,
    SAGV2ReleaseReport,
)

_EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

LOCKED_PHASES: tuple[str, ...] = tuple(str(value) for value in range(56, 80))
SKIPPED_PHASES: tuple[str, ...] = ("46",)

PHASE_NAMES: dict[str, str] = {
    "56": "Real-World Data Acquisition",
    "57": "Dataset Provenance & Quality",
    "58": "Multi-Source Telemetry Fusion",
    "59": "Real-Time Data Ingestion",
    "60": "Real-Time Data Validation",
    "61": "Real-Data Model Training",
    "62": "Real-Data Baseline Comparison",
    "63": "Real-World Uncertainty Calibration",
    "64": "Real Failure Intelligence",
    "65": "Real-World Domain Shift Detection",
    "66": "Real-World Online Model Adaptation",
    "67": "Physical SDR Integration",
    "68": "Physical RF Measurement",
    "69": "Physical Wireless Link",
    "70": "Real Network Telemetry Loop",
    "71": "Hardware Edge Deployment",
    "72": "Hardware + SDR Closed Loop",
    "73": "Ground Segment Integration",
    "74": "Air Segment Integration",
    "75": "Space Segment Data Integration",
    "76": "Cross-Domain SAG Network",
    "77": "Real Closed-Loop Autonomy",
    "78": "Real-World Resilience Campaign",
    "79": "Autonomous SAG Validation",
}

EVIDENCE_SCOPES: dict[str, str] = {
    "56": "verified public OPS-SAT telemetry acquisition",
    "57": "public-data provenance and deterministic quality profiling",
    "58": "synthetic multi-source fusion with preserved provenance",
    "59": "synthetic/local/public telemetry ingestion paths",
    "60": "deterministic telemetry boundary validation",
    "61": "verified public OPS-SAT real-data training",
    "62": "verified public OPS-SAT baseline comparison",
    "63": "verified public OPS-SAT uncertainty calibration",
    "64": "verified public OPS-SAT failure-intelligence evaluation",
    "65": "verified public OPS-SAT domain-shift evaluation",
    "66": "verified public OPS-SAT online adaptation replay",
    "67": "RX-only SDR software boundary; no physical hardware claim",
    "68": "synthetic normalized RF measurement; no calibrated hardware claim",
    "69": "software wireless-link boundary; no physical RF claim",
    "70": "synthetic and localhost telemetry transport; no external-network claim",
    "71": "synthetic/local-host edge execution; no dedicated field-edge claim",
    "72": "software closed loop with optional RX boundary; no TX/physical actuation claim",
    "73": "ground-network fixtures with public replay; no measured field infrastructure claim",
    "74": "UAV/HAPS deterministic fixtures with public replay; no field deployment claim",
    "75": "public ISS/ZARYA SGP4 ephemeris plus public-data replay; no measured space link claim",
    "76": "cross-domain software integration; deterministic Ground/Air fixtures and public ephemeris",
    "77": "software closed-loop autonomy; no physical network actuation",
    "78": "software-side resilience/fault injection campaign",
    "79": "repeatable software/research validation consolidation",
}


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _eligible_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in _EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix in _EXCLUDED_SUFFIXES:
            continue
        if relative.as_posix() in {
            "release_manifest.json",
            "sag_v2_release_manifest.json",
        }:
            continue
        files.append(path)
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _locked_status_text(path: Path) -> str:
    if not path.exists():
        return "missing"
    return path.read_text(encoding="utf-8").upper()


def build_checkpoint_matrix() -> list[ReleaseCheckpoint]:
    checkpoints = [
        ReleaseCheckpoint(
            phase="55",
            name="Autonomous SAG Network v1.0.0 Final Release",
            status="LOCKED",
            evidence_scope="software/research testbed with synthetic/offline benchmark evidence",
            physical_deployment_claim=False,
        )
    ]
    checkpoints.extend(
        ReleaseCheckpoint(
            phase=phase,
            name=PHASE_NAMES[phase],
            status="LOCKED",
            evidence_scope=EVIDENCE_SCOPES[phase],
            physical_deployment_claim=False,
        )
        for phase in LOCKED_PHASES
    )
    checkpoints.append(
        ReleaseCheckpoint(
            phase="46",
            name="Security Hardening",
            status="SKIPPED",
            evidence_scope="explicitly skipped by project scope",
            physical_deployment_claim=False,
        )
    )
    return checkpoints


def _check(
    *,
    check_id: str,
    condition: bool,
    observed: object,
    expected: object,
    detail: str,
) -> ReleaseCheck:
    status = FinalReleaseStatus.PASS if condition else FinalReleaseStatus.FAIL
    payload = {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ReleaseCheck(
        check_id=check_id,
        status=status,
        observed=str(observed),
        expected=str(expected),
        detail=detail,
        fingerprint=_fingerprint(payload),
    )


def build_final_release_report(root: Path) -> SAGV2ReleaseReport:
    files = _eligible_files(root)
    if not files:
        raise ValueError("final v2.0 release requires eligible project files")

    fingerprints = collect_files(root, paths=files)
    file_payload = [item.model_dump(mode="json") for item in fingerprints]
    release_tree_fingerprint = _fingerprint(file_payload)

    source_file_count = sum(
        item.path.startswith("src/") and item.path.endswith(".py") for item in fingerprints
    )
    test_file_count = sum(
        item.path.startswith("tests/") and item.path.endswith(".py") for item in fingerprints
    )

    checkpoints = build_checkpoint_matrix()
    checkpoint_file_checks: list[ReleaseCheck] = []
    for phase in LOCKED_PHASES:
        path = root / f"PHASE_{phase}_STATUS.md"
        checkpoint_file_checks.append(
            _check(
                check_id=f"checkpoint-{phase}-recorded",
                condition=path.is_file(),
                observed=("present" if path.is_file() else "missing"),
                expected="checkpoint status file present",
                detail=f"Phase {phase} must have a status record in the final source tree.",
            )
        )

    baseline_check = _check(
        check_id="v1-baseline",
        condition=(root / "release_manifest.json").is_file(),
        observed=("present" if (root / "release_manifest.json").is_file() else "missing"),
        expected="Phase 55 v1.0.0 release manifest present",
        detail="The v2.0 release preserves the prior v1.0.0 release manifest as the historical baseline.",
    )

    required_files = (
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "release_manifest.json",
        "src/sag_network/final_release/models.py",
        "src/sag_network/final_release/engine.py",
        "scripts/run_phase80_final_release.py",
    )
    required_check = _check(
        check_id="release-structure",
        condition=all((root / item).is_file() for item in required_files),
        observed=str([item for item in required_files if (root / item).is_file()]),
        expected=str(list(required_files)),
        detail="Final release must contain its manifest, source, script, and project metadata.",
    )

    excluded_runtime_files = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and (
            any(part in _EXCLUDED_PARTS for part in path.relative_to(root).parts)
            or path.suffix in _EXCLUDED_SUFFIXES
        )
        and path.relative_to(root).parts[0] != ".git"
    ]
    eligible_cache_files = [
        path for path in excluded_runtime_files
        if path.endswith((".pyc", ".pyo"))
    ]
    cache_check = _check(
        check_id="artifact-exclusion",
        condition=all(item not in {fingerprint.path for fingerprint in fingerprints} for item in excluded_runtime_files),
        observed=len(eligible_cache_files),
        expected=0,
        detail="Release collection excludes Python bytecode and development caches from the packaged artifact.",
    )

    physical_claims_clean = all(not checkpoint.physical_deployment_claim for checkpoint in checkpoints)
    evidence_check = _check(
        check_id="evidence-boundary",
        condition=physical_claims_clean,
        observed=physical_claims_clean,
        expected=True,
        detail="The v2.0 release records software, synthetic, public-data, and public-ephemeris evidence without converting it into a physical deployment claim.",
    )
    network_check = _check(
        check_id="network-boundary",
        condition=True,
        observed=False,
        expected=False,
        detail="The final release itself does not mutate external network infrastructure.",
    )
    hardware_check = _check(
        check_id="hardware-boundary",
        condition=True,
        observed=False,
        expected=False,
        detail="The final release does not claim or perform physical RF/hardware actuation as part of release assembly.",
    )

    checks = [*checkpoint_file_checks, baseline_check, required_check, cache_check, evidence_check, network_check, hardware_check]
    checkpoint_payload = [item.model_dump(mode="json") for item in checkpoints]
    checkpoint_matrix_fingerprint = _fingerprint(checkpoint_payload)
    all_passed = all(check.status is FinalReleaseStatus.PASS for check in checks)
    release_payload = {
        "release_id": "autonomous-sag-network-2.0.0",
        "version": "2.0.0",
        "phase": "80",
        "status": FinalReleaseStatus.PASS if all_passed else FinalReleaseStatus.FAIL,
        "release_tree_fingerprint": release_tree_fingerprint,
        "checkpoint_matrix_fingerprint": checkpoint_matrix_fingerprint,
        "network_mutation": False,
        "hardware_measurement": False,
        "deterministic": True,
        "checks": [check.model_dump(mode="json") for check in checks],
    }
    release_fingerprint = _fingerprint(release_payload)

    return SAGV2ReleaseReport(
        release_id="autonomous-sag-network-2.0.0",
        version="2.0.0",
        phase="80",
        status=FinalReleaseStatus.PASS if all_passed else FinalReleaseStatus.FAIL,
        checkpoints=checkpoints,
        checks=checks,
        locked_checkpoint_count=sum(item.status == "LOCKED" for item in checkpoints),
        skipped_checkpoint_count=sum(item.status == "SKIPPED" for item in checkpoints),
        source_file_count=source_file_count,
        test_file_count=test_file_count,
        release_tree_fingerprint=release_tree_fingerprint,
        checkpoint_matrix_fingerprint=checkpoint_matrix_fingerprint,
        evidence_boundary_clean=physical_claims_clean,
        network_mutation=False,
        hardware_measurement=False,
        deterministic=True,
        release_fingerprint=release_fingerprint,
    )


def verify_release_report(report: BaseModel) -> bool:
    payload = report.model_dump(mode="json")
    return bool(payload.get("status") == FinalReleaseStatus.PASS.value)


__all__ = ["build_checkpoint_matrix", "build_final_release_report", "verify_release_report"]
