from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sag_network.domain.unified import NetworkDomain
from sag_network.history.models import HistoricalQuery
from sag_network.history.store import HistoricalDatasetStore
from sag_network.predictive.deep_learning_models import DeepLearningConfig
from sag_network.predictive.failure_intelligence import PredictiveFailureIntelligence
from sag_network.predictive.failure_models import FailureThresholdRule
from sag_network.predictive.uncertainty import UncertaintyAwarePrediction
from sag_network.predictive.uncertainty_models import UncertaintyConfig
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase35-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:phase35",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=35.0 - 0.6 * index + 0.25 * ((index * 5) % 4 - 1),
            unit="dB",
            metadata={"fixture": "synthetic_phase35"},
        )
        for index in range(1, 41)
    ]


def main() -> None:
    records = _records()
    with tempfile.TemporaryDirectory(prefix="sag-phase35-") as directory:
        store = HistoricalDatasetStore(Path(directory))
        store.create("phase35-history")
        accepted = store.append("phase35-history", records)
        manifest = store.seal("phase35-history")
        queried = store.query("phase35-history", HistoricalQuery(limit=100))
        uncertainty = UncertaintyAwarePrediction(
            UncertaintyConfig(confidence_level=0.90, minimum_calibration_samples=5, horizon_growth=0.15),
            DeepLearningConfig(lag_steps=6, minimum_samples=20, hidden_units=6, epochs=100, horizon_steps=3),
        ).predict(queried.records, reference_time_s=40.0)
        report = PredictiveFailureIntelligence().analyze(
            uncertainty,
            reference_time_s=40.0,
            rules=[
                FailureThresholdRule(
                    metric=TelemetryMetric.SINR_DB,
                    minimum_value=20.0,
                    warning_within_s=5.0,
                    critical_within_s=2.0,
                )
            ],
        )
        payload = {
            "name": "Predictive Failure Intelligence",
            "phase": "35",
            "status": "pass" if report.predicted_failure_count > 0 else "fail",
            "accepted_records": accepted,
            "queried_records": queried.count,
            "dataset_status": manifest.status.value,
            "dataset_fingerprint": manifest.dataset_fingerprint,
            "calibrated_series": uncertainty.calibrated_count,
            "predicted_failure_count": report.predicted_failure_count,
            "findings": [
                {
                    "event_id": finding.event_id,
                    "direction": finding.direction.value,
                    "risk_level": finding.risk_level.value,
                    "lead_time_s": finding.lead_time_s,
                    "predicted_value": finding.predicted_value,
                    "threshold_value": finding.threshold_value,
                    "risk_score": finding.risk_score,
                    "uncertainty_score": finding.uncertainty_score,
                }
                for series in report.series
                for finding in series.predicted_failures
            ],
            "fixture": "synthetic historical telemetry fixture",
            "state_mutation": False,
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
