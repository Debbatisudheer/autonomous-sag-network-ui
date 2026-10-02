from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.history.models import HistoricalQuery
from sag_network.history.store import HistoricalDatasetStore
from sag_network.predictive.deep_learning_models import DeepLearningConfig
from sag_network.predictive.uncertainty import UncertaintyAwarePrediction
from sag_network.predictive.uncertainty_models import UncertaintyConfig
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase34-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:phase34",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=40.0 - 0.4 * index + 0.35 * ((index * 7) % 5 - 2),
            unit="dB",
            metadata={"fixture": "synthetic_phase34"},
        )
        for index in range(1, 41)
    ]


def main() -> None:
    records = _records()
    with tempfile.TemporaryDirectory(prefix="sag-phase34-") as directory:
        store = HistoricalDatasetStore(Path(directory))
        store.create("phase34-history")
        accepted = store.append("phase34-history", records)
        manifest = store.seal("phase34-history")
        queried = store.query("phase34-history", HistoricalQuery(limit=100))
        report = UncertaintyAwarePrediction(
            UncertaintyConfig(confidence_level=0.90, minimum_calibration_samples=5, horizon_growth=0.15),
            DeepLearningConfig(lag_steps=6, minimum_samples=20, hidden_units=6, epochs=100, horizon_steps=3),
        ).predict(queried.records, reference_time_s=40.0)
        series = report.series[0]
        payload = {
            "name": "Uncertainty-Aware Prediction",
            "phase": "34",
            "status": "pass" if series.intervals and series.status.value == "calibrated" else "fail",
            "accepted_records": accepted,
            "queried_records": queried.count,
            "dataset_status": manifest.status.value,
            "dataset_fingerprint": manifest.dataset_fingerprint,
            "calibrated_series": report.calibrated_count,
            "calibration_samples": series.calibration_samples,
            "confidence_level": report.config.confidence_level,
            "calibration_quantile": series.calibration_quantile,
            "intervals": [
                {
                    "horizon_s": item.horizon_s,
                    "predicted_value": item.predicted_value,
                    "lower_bound": item.lower_bound,
                    "upper_bound": item.upper_bound,
                    "interval_width": item.interval_width,
                    "uncertainty_score": item.uncertainty_score,
                }
                for item in series.intervals
            ],
            "fixture": "synthetic historical telemetry fixture",
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
