from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path

from sag_network.real_training import RealDataModelTrainer, RealDataTrainingConfig
from sag_network.real_training.models import TrainingEvidence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "raw" / "opssat-ad" / "segments.csv"


def _fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train"])
        for index in range(60):
            writer.writerow([index, "fixture-channel", 20.0 - 0.25 * index, 1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opssat-file", type=Path, default=None)
    args = parser.parse_args()
    if args.opssat_file is not None:
        report = RealDataModelTrainer().train_csv(args.opssat_file)
    else:
        with tempfile.TemporaryDirectory(prefix="sag-phase61-") as directory:
            dataset = Path(directory) / "segments.csv"
            _fixture(dataset)
            report = RealDataModelTrainer().train_csv(
                dataset,
                config=RealDataTrainingConfig(minimum_samples=20),
                evidence_class=TrainingEvidence.SYNTHETIC_FIXTURE,
            )
    print(
        json.dumps(
            {
                **report.model_dump(mode="json"),
                "network_mutation": False,
                "notice": "Default run uses an offline fixture. Pass --opssat-file only with the verified public OPS-SAT dataset.",
                "dataset_sha256": report.source_sha256,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
