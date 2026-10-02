from __future__ import annotations

import argparse
from pathlib import Path

from sag_network.online_adaptation import (
    OnlineAdaptationConfig,
    OnlineAdaptationEvidence,
    RealOnlineModelAdaptationRunner,
)


def _fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("timestamp,channel,value,train,anomaly,label\n")
        values = [10.0 + (index % 5) * 0.1 for index in range(80)]
        values.extend(20.0 + (index % 5) * 0.1 for index in range(40))
        for index, value in enumerate(values):
            stream.write(f"{index},channel-a,{value},1,0,normal\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 66 online model adaptation")
    parser.add_argument("--opssat-file", type=Path)
    args = parser.parse_args()
    evidence = OnlineAdaptationEvidence.PUBLIC_DATA
    if args.opssat_file is None:
        path = Path("data/runtime/phase66-fixture.csv")
        _fixture(path)
        evidence = OnlineAdaptationEvidence.SYNTHETIC_FIXTURE
    else:
        path = args.opssat_file
    report = RealOnlineModelAdaptationRunner().run(
        path,
        config=OnlineAdaptationConfig(),
        evidence_class=evidence,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
