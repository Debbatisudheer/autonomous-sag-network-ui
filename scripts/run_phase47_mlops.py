from __future__ import annotations

import hashlib
import json

from sag_network.domain.unified import NetworkDomain
from sag_network.mlops import (
    build_model_artifact,
    DatasetLineage,
    MLOpsRegistry,
    ModelEvaluation,
    PromotionGate,
)
from sag_network.predictive.ml_baseline import MLPredictiveBaseline
from sag_network.predictive.ml_models import MLBaselineConfig
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _dataset_fingerprint(records: list[TelemetryRecord]) -> str:
    payload = [record.model_dump(mode="json") for record in records]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    records = [
        TelemetryRecord(
            record_id=f"phase47-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="uav-a:ml-01",
            domain=NetworkDomain.AIR,
            metric=TelemetryMetric.SINR_DB,
            value=float(21 - index),
            unit="dB",
        )
        for index in range(1, 25)
    ]
    config = MLBaselineConfig(lag_steps=3, minimum_samples=8, horizon_steps=3)
    training_report = MLPredictiveBaseline(config).train_and_forecast(
        records, reference_time_s=24.0
    )
    series = training_report.series[0]
    if series.model is None:
        raise RuntimeError("phase 47 training fixture did not produce a model")
    model = series.model
    evaluation = ModelEvaluation(
        mean_absolute_error=model.metrics.mean_absolute_error,
        root_mean_squared_error=model.metrics.root_mean_squared_error,
        r_squared=model.metrics.r_squared,
        training_samples=model.metrics.train_samples,
        test_samples=model.metrics.test_samples,
    )
    lineage = DatasetLineage(
        dataset_id="phase47-telemetry-fixture",
        dataset_fingerprint=_dataset_fingerprint(records),
        source="synthetic historical telemetry fixture",
        record_count=len(records),
        fixture="synthetic historical telemetry fixture",
    )
    artifact = build_model_artifact(
        model_id="sinr-baseline",
        version="47.1.0",
        model_type="ridge-telemetry-baseline",
        model_fingerprint=model.model_fingerprint,
        dataset_lineage=lineage,
        feature_schema=model.feature_names,
        training_config=config.model_dump(mode="json"),
        evaluation=evaluation,
    )
    registry = MLOpsRegistry()
    registry.register(artifact)
    gate = PromotionGate(
        minimum_r_squared=0.9,
        maximum_root_mean_squared_error=1e-6,
        minimum_test_samples=4,
    )
    decision = registry.promote(artifact.model_id, artifact.version, gate)
    if not decision.eligible:
        raise RuntimeError("phase 47 MLOps promotion gate failed")
    report = registry.report(
        timestamp_s=47.0,
        fixture="synthetic offline MLOps fixture",
        decision=decision,
    )
    print(json.dumps({
        "name": "MLOps",
        "phase": "47",
        "status": "pass",
        "registered_models": report.registered_models,
        "production_models": report.production_models,
        "rejected_models": report.rejected_models,
        "model_id": report.promoted_model_id,
        "model_version": report.promoted_version,
        "dataset_fingerprint": lineage.dataset_fingerprint,
        "model_fingerprint": model.model_fingerprint,
        "artifact_fingerprint": artifact.artifact_fingerprint,
        "r_squared": evaluation.r_squared,
        "rmse": evaluation.root_mean_squared_error,
        "test_samples": evaluation.test_samples,
        "registry_fingerprint": report.registry_fingerprint,
        "promotion_fingerprint": report.promotion_fingerprint,
        "model_deployed_externally": False,
        "network_mutation": False,
        "fixture": "synthetic offline MLOps fixture",
    }, indent=2))


if __name__ == "__main__":
    main()
