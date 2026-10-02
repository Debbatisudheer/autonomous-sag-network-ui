from __future__ import annotations

import json
from pathlib import Path

from sag_network.final_release import build_final_release_report

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "sag_v2_release_manifest.json"


def main() -> None:
    report = build_final_release_report(ROOT)
    MANIFEST_PATH.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "name": "SAG v2.0 Final Real-World Release",
                "phase": "80",
                "status": report.status,
                "release_id": report.release_id,
                "version": report.version,
                "locked_checkpoint_count": report.locked_checkpoint_count,
                "skipped_checkpoint_count": report.skipped_checkpoint_count,
                "source_file_count": report.source_file_count,
                "test_file_count": report.test_file_count,
                "release_tree_fingerprint": report.release_tree_fingerprint,
                "checkpoint_matrix_fingerprint": report.checkpoint_matrix_fingerprint,
                "evidence_boundary_clean": report.evidence_boundary_clean,
                "network_mutation": report.network_mutation,
                "hardware_measurement": report.hardware_measurement,
                "deterministic": report.deterministic,
                "release_fingerprint": report.release_fingerprint,
                "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
