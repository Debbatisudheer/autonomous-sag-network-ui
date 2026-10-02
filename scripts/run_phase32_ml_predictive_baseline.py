from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.history.models import HistoricalQuery
from sag_network.history.store import HistoricalDatasetStore
from sag_network.predictive.ml_baseline import MLPredictiveBaseline
from sag_network.predictive.ml_models import MLBaselineConfig
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase32-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:phase32",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=30.0 - float(index),
            unit="dB",
            metadata={"fixture": "synthetic_phase32"},
        )
        for index in range(1, 25)
    ]


def main() -> None:
    records = _records()
    with tempfile.TemporaryDirectory(prefix="sag-phase32-") as directory:
        store = HistoricalDatasetStore(Path(directory))
        store.create("phase32-history")
        accepted = store.append("phase32-history", records)
        manifest = store.seal("phase32-history")
        queried = store.query("phase32-history", HistoricalQuery(limit=100))
        report = MLPredictiveBaseline(
            MLBaselineConfig(lag_steps=3, minimum_samples=12, horizon_steps=3)
        ).train_and_forecast(queried.records, reference_time_s=24.0)
        series = report.series[0]
        payload = {
            "name": "ML Predictive Baseline",
            "phase": "32",
            "status": "pass" if series.model is not None and series.forecasts else "fail",
            "accepted_records": accepted,
            "queried_records": queried.count,
            "dataset_status": manifest.status.value,
            "dataset_fingerprint": manifest.dataset_fingerprint,
            "trained_series": report.trained_count,
            "training_samples": series.model.training_samples if series.model else 0,
            "test_samples": series.model.metrics.test_samples if series.model else 0,
            "mae": series.model.metrics.mean_absolute_error if series.model else None,
            "rmse": series.model.metrics.root_mean_squared_error if series.model else None,
            "r_squared": series.model.metrics.r_squared if series.model else None,
            "model_fingerprint": series.model.model_fingerprint if series.model else None,
            "forecast_values": [item.predicted_value for item in series.forecasts],
            "fixture": "synthetic historical telemetry fixture",
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
