from __future__ import annotations

import argparse
import json
from pathlib import Path

from sag_network.data_quality import DatasetQualityError, profile_csv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "raw" / "opssat-ad" / "segments.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the acquired real OPS-SAT telemetry dataset")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()

    try:
        report = profile_csv(args.dataset)
    except DatasetQualityError as exc:
        print(json.dumps({"name": "Dataset Provenance & Quality", "phase": "57", "status": "error", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc

    output = ROOT / "data" / "quality" / "opssat-ad-quality-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.to_json() + "\n", encoding="utf-8")

    print(json.dumps({
        "name": "Dataset Provenance & Quality",
        "phase": "57",
        "status": "pass",
        "dataset": report.dataset_name,
        "evidence_class": "PUBLIC DATA",
        "row_count": report.row_count,
        "column_count": report.column_count,
        "duplicate_row_count": report.duplicate_row_count,
        "empty_row_count": report.empty_row_count,
        "numeric_column_count": len(report.numeric_columns),
        "timestamp_columns": list(report.timestamp_columns),
        "label_columns": list(report.label_columns),
        "split_columns": list(report.split_columns),
        "source_sha256": report.source_sha256,
        "quality_fingerprint": report.quality_fingerprint,
        "provenance_manifest": report.provenance_manifest,
        "provenance_source_uri": report.provenance_source_uri,
        "provenance_source_page": report.provenance_source_page,
        "provenance_md5": report.provenance_md5,
        "provenance_verified": report.provenance_verified,
        "network_mutation": False,
        "report": output.relative_to(ROOT).as_posix(),
    }, indent=2))


if __name__ == "__main__":
    main()
