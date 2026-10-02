from __future__ import annotations

import json

from sag_network.validation.runner import run_validation_matrix


def main() -> None:
    report = run_validation_matrix()
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
