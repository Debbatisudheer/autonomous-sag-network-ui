from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sag_network.baseline_comparison import BaselineComparisonConfig, BaselineComparisonRunner
from sag_network.domain.unified import NetworkDomain
from sag_network.history.models import HistoricalQuery
from sag_network.history.store import HistoricalDatasetStore
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    values = [
        30.0,
        29.5,
        28.7,
        28.0,
        27.1,
        26.4,
        25.2,
        24.5,
        23.7,
        22.8,
        22.0,
        21.2,
        20.5,
        19.7,
        18.8,
        18.1,
        17.4,
        16.6,
        15.9,
        15.1,
        14.4,
        13.7,
        13.0,
        12.2,
    ]
    return [
        TelemetryRecord(
            record_id=f"phase50-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:phase50",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=value,
            unit="dB",
            metadata={"fixture": "synthetic_phase50"},
        )
        for index, value in enumerate(values, start=1)
    ]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sag-phase50-") as directory:
        store = HistoricalDatasetStore(Path(directory))
        store.create("phase50-history")
        accepted = store.append("phase50-history", records())
        manifest = store.seal("phase50-history")
        queried = store.query("phase50-history", HistoricalQuery(limit=100))
        result = BaselineComparisonRunner().run(
            queried.records,
            experiment_id="phase50-wireless-baseline-comparison",
            config=BaselineComparisonConfig(
                lag_steps=3,
                minimum_training_samples=12,
                rolling_window=3,
                holdout_size=6,
            ),
            fixture="synthetic offline baseline-comparison fixture",
        )
        print(
            json.dumps(
                {
                    "name": "Baseline Comparison",
                    "phase": "50",
                    "status": "pass",
                    "accepted_records": accepted,
                    "queried_records": queried.count,
                    "dataset_status": manifest.status.value,
                    "dataset_fingerprint": manifest.dataset_fingerprint,
                    "training_count": result.training_count,
                    "holdout_count": result.holdout_count,
                    "method_count": len(result.metric_results),
                    "methods": [item.method.value for item in result.metric_results],
                    "comparisons": [item.model_dump(mode="json") for item in result.comparisons],
                    "result_fingerprint": result.result_fingerprint,
                    "network_mutation": False,
                    "fixture": result.fixture,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
