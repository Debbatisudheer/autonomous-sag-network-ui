from __future__ import annotations

import argparse
import json
from pathlib import Path

from sag_network.real_baseline_comparison import RealDataBaselineComparisonRunner

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "raw" / "opssat-ad" / "segments.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opssat-file", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    report = RealDataBaselineComparisonRunner().run(args.opssat_file)
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
