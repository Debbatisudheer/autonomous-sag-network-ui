from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.history.models import HistoricalQuery
from sag_network.history.store import HistoricalDatasetStore
from sag_network.predictive.deep_learning_models import DeepLearningConfig
from sag_network.predictive.time_series_deep_learning import TimeSeriesDeepLearning
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase33-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:phase33",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=40.0 - 0.4 * index + 0.01 * (index % 3),
            unit="dB",
            metadata={"fixture": "synthetic_phase33"},
        )
        for index in range(1, 41)
    ]


def main() -> None:
    records = _records()
    with tempfile.TemporaryDirectory(prefix="sag-phase33-") as directory:
        store = HistoricalDatasetStore(Path(directory))
        store.create("phase33-history")
        accepted = store.append("phase33-history", records)
        manifest = store.seal("phase33-history")
        queried = store.query("phase33-history", HistoricalQuery(limit=100))
        report = TimeSeriesDeepLearning(
            DeepLearningConfig(lag_steps=6, minimum_samples=20, hidden_units=6, epochs=100, horizon_steps=3)
        ).train_and_forecast(queried.records, reference_time_s=40.0)
        series = report.series[0]
        payload = {
            "name": "Time-Series Deep Learning",
            "phase": "33",
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
            "train_loss": series.model.metrics.train_loss if series.model else None,
            "hidden_units": series.model.hidden_units if series.model else None,
            "model_fingerprint": series.model.model_fingerprint if series.model else None,
            "forecast_values": [item.predicted_value for item in series.forecasts],
            "fixture": "synthetic historical telemetry fixture",
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
