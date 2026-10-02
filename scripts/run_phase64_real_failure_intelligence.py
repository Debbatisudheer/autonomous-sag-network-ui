from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

from sag_network.real_failure_intelligence import (
    RealFailureEvidence,
    RealFailureIntelligenceConfig,
    RealFailureIntelligenceRunner,
)


def _fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        for index in range(140):
            anomaly = int(index >= 112)
            value = 20.0 + 0.05 * index
            if anomaly:
                value += 15.0
            writer.writerow([index, "fixture-channel", value, 1, anomaly, "anomaly" if anomaly else "normal"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opssat-file", type=Path, default=None)
    args = parser.parse_args()
    if args.opssat_file is not None:
        report = RealFailureIntelligenceRunner().run(args.opssat_file)
    else:
        with tempfile.TemporaryDirectory(prefix="sag-phase64-") as directory:
            dataset = Path(directory) / "segments.csv"
            _fixture(dataset)
            report = RealFailureIntelligenceRunner().run(
                dataset,
                config=RealFailureIntelligenceConfig(minimum_calibration_samples=10),
                evidence_class=RealFailureEvidence.SYNTHETIC_FIXTURE,
            )
    print(
        json.dumps(
            {
                **report.model_dump(mode="json"),
                "network_mutation": False,
                "notice": (
                    "Default run uses an offline synthetic fixture. "
                    "Pass --opssat-file only with the verified public OPS-SAT dataset. "
                    "Observed anomaly labels are used only for post-hoc evaluation; "
                    "they are not used to fit the predictive model."
                ),
                "dataset_sha256": report.source_sha256,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
