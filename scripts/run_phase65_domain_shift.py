from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

from sag_network.real_domain_shift import (
    DomainShiftConfig,
    DomainShiftEvidence,
    RealDomainShiftRunner,
)


def _fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train", "anomaly", "label"])
        for index in range(200):
            if index < 160:
                value = 10.0 + 0.01 * index
            else:
                value = 25.0 + 0.01 * index
            writer.writerow([index, "fixture-channel", value, 1, 0, "normal"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opssat-file", type=Path, default=None)
    args = parser.parse_args()
    if args.opssat_file is not None:
        report = RealDomainShiftRunner().run(args.opssat_file)
    else:
        with tempfile.TemporaryDirectory(prefix="sag-phase65-") as directory:
            dataset = Path(directory) / "segments.csv"
            _fixture(dataset)
            report = RealDomainShiftRunner().run(
                dataset,
                config=DomainShiftConfig(minimum_comparison_samples=10),
                evidence_class=DomainShiftEvidence.SYNTHETIC_FIXTURE,
            )
    print(
        json.dumps(
            {
                **report.model_dump(mode="json"),
                "network_mutation": False,
                "notice": (
                    "Default run uses an offline synthetic fixture. "
                    "Pass --opssat-file only with the verified public OPS-SAT dataset. "
                    "Observed anomaly labels are not used by the detector."
                ),
                "dataset_sha256": report.source_sha256,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
