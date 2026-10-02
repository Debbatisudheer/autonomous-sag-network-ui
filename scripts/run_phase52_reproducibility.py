from __future__ import annotations

import json
import platform
from pathlib import Path

from sag_network.reproducibility import build_manifest, verify_manifest


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = build_manifest(
        root,
        package_id="phase52-sag-research-package",
        phase="52",
        commands=(
            "ruff check .",
            "mypy src",
            "pytest -q",
            "python scripts\\run_phase52_reproducibility.py",
        ),
        runtime={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        },
        evidence_class="synthetic offline reproducibility fixture",
        notes=(
            "Source fingerprints exclude VCS and Python cache directories.",
            "Verification is content-based and deterministic.",
            "This package does not claim external deployment or physical measurement reproducibility.",
        ),
    )
    check = verify_manifest(root, manifest)
    print(
        json.dumps(
            {
                "name": "Reproducibility & Research Package",
                "phase": "52",
                "status": "pass" if check.reproducible else "fail",
                "package_id": manifest.package_id,
                "source_file_count": len(manifest.source_files),
                "matched_files": check.matched_files,
                "missing_files": list(check.missing_files),
                "changed_or_extra_files": list(check.changed_files),
                "manifest_fingerprint": manifest.manifest_fingerprint,
                "verification_fingerprint": check.verification_fingerprint,
                "reproducible": check.reproducible,
                "fixture": "synthetic offline reproducibility fixture",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
