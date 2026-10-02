from __future__ import annotations

import pytest

from sag_network.mlops import (
    build_model_artifact,
    DatasetLineage,
    MLOpsRegistry,
    MLOpsStage,
    ModelEvaluation,
    PromotionGate,
)


def artifact(*, rmse: float = 0.0, r_squared: float = 1.0):
    return build_model_artifact(
        model_id="sinr-baseline",
        version="32.1.0",
        model_type="ridge-telemetry-baseline",
        model_fingerprint="a" * 64,
        dataset_lineage=DatasetLineage(
            dataset_id="phase32-fixture",
            dataset_fingerprint="b" * 64,
            source="synthetic historical telemetry fixture",
            record_count=24,
            fixture="synthetic historical telemetry fixture",
        ),
        feature_schema=("lag_1", "lag_2", "lag_3", "delta_1", "rolling_mean"),
        training_config={"lag_steps": 3, "ridge_alpha": 1e-6},
        evaluation=ModelEvaluation(
            mean_absolute_error=0.0,
            root_mean_squared_error=rmse,
            r_squared=r_squared,
            training_samples=15,
            test_samples=6,
        ),
    )


def test_artifact_fingerprint_is_deterministic() -> None:
    assert artifact().artifact_fingerprint == artifact().artifact_fingerprint


def test_registry_promotes_eligible_model() -> None:
    registry = MLOpsRegistry()
    registry.register(artifact())
    decision = registry.promote(
        "sinr-baseline",
        "32.1.0",
        PromotionGate(
            minimum_r_squared=0.9,
            maximum_root_mean_squared_error=0.1,
            minimum_test_samples=5,
        ),
    )
    assert decision.eligible
    assert registry.get("sinr-baseline", "32.1.0").stage is MLOpsStage.PRODUCTION


def test_registry_rejects_model_below_gate() -> None:
    registry = MLOpsRegistry()
    registry.register(artifact(rmse=2.0, r_squared=0.2))
    decision = registry.promote(
        "sinr-baseline",
        "32.1.0",
        PromotionGate(
            minimum_r_squared=0.9,
            maximum_root_mean_squared_error=0.1,
            minimum_test_samples=5,
        ),
    )
    assert not decision.eligible
    assert decision.reasons == ("r_squared_below_minimum", "rmse_above_maximum")
    assert registry.get("sinr-baseline", "32.1.0").stage is MLOpsStage.REJECTED


def test_registry_does_not_allow_duplicate_version() -> None:
    registry = MLOpsRegistry()
    registry.register(artifact())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(artifact())


def test_promotion_replaces_existing_production_version() -> None:
    registry = MLOpsRegistry()
    first = artifact()
    second = first.model_copy(update={"version": "32.2.0", "artifact_fingerprint": "c" * 64})
    registry.register(first)
    registry.register(second)
    gate = PromotionGate(
        minimum_r_squared=0.9,
        maximum_root_mean_squared_error=0.1,
        minimum_test_samples=5,
    )
    registry.promote(first.model_id, first.version, gate)
    registry.promote(second.model_id, second.version, gate)
    assert registry.get(first.model_id, first.version).stage is MLOpsStage.VALIDATED
    assert registry.get(second.model_id, second.version).stage is MLOpsStage.PRODUCTION


def test_report_counts_lifecycle_stages() -> None:
    registry = MLOpsRegistry()
    registry.register(artifact())
    decision = registry.promote(
        "sinr-baseline",
        "32.1.0",
        PromotionGate(
            minimum_r_squared=0.9,
            maximum_root_mean_squared_error=0.1,
            minimum_test_samples=5,
        ),
    )
    report = registry.report(
        timestamp_s=47.0,
        fixture="synthetic offline MLOps fixture",
        decision=decision,
    )
    assert report.registered_models == 1
    assert report.validated_models == 0
    assert report.production_models == 1
    assert report.rejected_models == 0
