from __future__ import annotations

import json
from pathlib import Path

from sag_network.release import build_release_manifest
from sag_network.release.manifest import current_runtime

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release_manifest.json"

PHASE54_BENCHMARK_FINGERPRINT = (
    "089bddd7512758b24f2a4c0798a5f3833cd8a9035493dda571d136816dbeabc4"
)

EXCLUDED_ARTIFACTS = (
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "*.pyc",
    "*.pyo",
)


def main() -> None:
    manifest = build_release_manifest(
        ROOT,
        version="1.0.0",
        phase54_benchmark_fingerprint=PHASE54_BENCHMARK_FINGERPRINT,
        evidence_class=(
            "software/research testbed; "
            "synthetic/offline benchmark evidence explicitly labeled"
        ),
        network_mutation=False,
        excluded_artifacts=EXCLUDED_ARTIFACTS,
        runtime=current_runtime(),
    )

    MANIFEST_PATH.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "name": "Final Release",
                "phase": "55",
                "status": "pass",
                "release_id": manifest.release_id,
                "version": manifest.version,
                "source_file_count": manifest.source_file_count,
                "test_file_count": manifest.test_file_count,
                "source_tree_fingerprint": (
                    manifest.source_tree_fingerprint
                ),
                "phase54_benchmark_fingerprint": (
                    manifest.phase54_benchmark_fingerprint
                ),
                "release_fingerprint": manifest.release_fingerprint,
                "deterministic": manifest.deterministic,
                "network_mutation": manifest.network_mutation,
                "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()