from __future__ import annotations

import argparse
import json
from pathlib import Path

from sag_network.real_data import acquire_public_dataset, OPS_SAT_AD_V2

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = ROOT / "data" / "raw" / "opssat-ad" / "segments.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 56 public real-data acquisition")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()

    result: dict[str, object] = {
        "name": "Real-World Data Acquisition",
        "phase": "56",
        "status": "pass",
        "dataset": OPS_SAT_AD_V2.name,
        "version": OPS_SAT_AD_V2.version,
        "evidence_class": OPS_SAT_AD_V2.evidence_class,
        "source_page": OPS_SAT_AD_V2.source_page,
        "download_required": not args.download,
        "network_mutation": False,
    }

    if args.download:
        result.update(
            acquire_public_dataset(
                OPS_SAT_AD_V2,
                args.destination,
            )
        )
    else:
        result["notice"] = "Run with --download on a network-enabled machine to acquire and verify the public dataset."

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
