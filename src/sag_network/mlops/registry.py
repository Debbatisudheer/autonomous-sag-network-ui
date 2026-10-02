from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from sag_network.mlops.models import (
    DatasetLineage,
    MLOpsReport,
    MLOpsStage,
    ModelArtifact,
    ModelEvaluation,
    PromotionDecision,
    PromotionGate,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class MLOpsRegistry:
    """In-memory deterministic registry and promotion gate for learned artifacts."""

    def __init__(self) -> None:
        self._artifacts: dict[tuple[str, str], ModelArtifact] = {}

    def register(self, artifact: ModelArtifact) -> ModelArtifact:
        key = (artifact.model_id, artifact.version)
        if key in self._artifacts:
            raise ValueError(
                f"model version already registered: {artifact.model_id}:{artifact.version}"
            )
        self._artifacts[key] = artifact
        return artifact

    def get(self, model_id: str, version: str) -> ModelArtifact:
        try:
            return self._artifacts[(model_id, version)]
        except KeyError as exc:
            raise KeyError(f"model version not found: {model_id}:{version}") from exc

    def evaluate(self, model_id: str, version: str, gate: PromotionGate) -> PromotionDecision:
        artifact = self.get(model_id, version)
        evaluation = artifact.evaluation
        reasons: list[str] = []
        if evaluation.r_squared < gate.minimum_r_squared:
            reasons.append("r_squared_below_minimum")
        if evaluation.root_mean_squared_error > gate.maximum_root_mean_squared_error:
            reasons.append("rmse_above_maximum")
        if evaluation.test_samples < gate.minimum_test_samples:
            reasons.append("test_samples_below_minimum")
        eligible = not reasons
        resulting_stage = MLOpsStage.VALIDATED if eligible else MLOpsStage.REJECTED
        updated = artifact.model_copy(update={"stage": resulting_stage})
        self._artifacts[(model_id, version)] = updated
        decision_payload = {
            "model_id": model_id,
            "version": version,
            "eligible": eligible,
            "previous_stage": artifact.stage.value,
            "resulting_stage": resulting_stage.value,
            "reasons": reasons,
        }
        return PromotionDecision(
            model_id=model_id,
            version=version,
            eligible=eligible,
            previous_stage=artifact.stage,
            resulting_stage=resulting_stage,
            reasons=tuple(reasons),
            decision_fingerprint=_fingerprint(decision_payload),
        )

    def promote(self, model_id: str, version: str, gate: PromotionGate) -> PromotionDecision:
        decision = self.evaluate(model_id, version, gate)
        if not decision.eligible:
            return decision
        artifact = self.get(model_id, version)
        for key, candidate in tuple(self._artifacts.items()):
            if key[0] == model_id and candidate.stage is MLOpsStage.PRODUCTION:
                self._artifacts[key] = candidate.model_copy(update={"stage": MLOpsStage.VALIDATED})
        self._artifacts[(model_id, version)] = artifact.model_copy(
            update={"stage": MLOpsStage.PRODUCTION}
        )
        return decision.model_copy(update={"resulting_stage": MLOpsStage.PRODUCTION})

    def report(
        self, *, timestamp_s: float, fixture: str, decision: PromotionDecision
    ) -> MLOpsReport:
        artifacts = tuple(self._artifacts.values())
        registry_payload = [
            {
                "model_id": artifact.model_id,
                "version": artifact.version,
                "stage": artifact.stage.value,
                "artifact_fingerprint": artifact.artifact_fingerprint,
            }
            for artifact in sorted(artifacts, key=lambda item: (item.model_id, item.version))
        ]
        promoted = [artifact for artifact in artifacts if artifact.stage is MLOpsStage.PRODUCTION]
        return MLOpsReport(
            timestamp_s=timestamp_s,
            registered_models=len(artifacts),
            validated_models=sum(item.stage is MLOpsStage.VALIDATED for item in artifacts),
            production_models=len(promoted),
            rejected_models=sum(item.stage is MLOpsStage.REJECTED for item in artifacts),
            promoted_model_id=promoted[0].model_id if promoted else None,
            promoted_version=promoted[0].version if promoted else None,
            registry_fingerprint=_fingerprint(registry_payload),
            promotion_fingerprint=decision.decision_fingerprint,
            fixture=fixture,
        )


def build_model_artifact(
    *,
    model_id: str,
    version: str,
    model_type: str,
    model_fingerprint: str,
    dataset_lineage: DatasetLineage,
    feature_schema: Iterable[str],
    training_config: object,
    evaluation: ModelEvaluation,
) -> ModelArtifact:
    """Create reproducible registry metadata without storing model weights."""
    feature_schema_fingerprint = _fingerprint(list(feature_schema))
    training_config_fingerprint = _fingerprint(training_config)
    payload = {
        "model_id": model_id,
        "version": version,
        "model_type": model_type,
        "model_fingerprint": model_fingerprint,
        "dataset_lineage": dataset_lineage.model_dump(mode="json"),
        "feature_schema_fingerprint": feature_schema_fingerprint,
        "training_config_fingerprint": training_config_fingerprint,
        "evaluation": evaluation.model_dump(mode="json"),
    }
    return ModelArtifact(
        model_id=model_id,
        version=version,
        model_type=model_type,
        model_fingerprint=model_fingerprint,
        dataset_lineage=dataset_lineage,
        feature_schema_fingerprint=feature_schema_fingerprint,
        training_config_fingerprint=training_config_fingerprint,
        evaluation=evaluation,
        artifact_fingerprint=_fingerprint(payload),
    )
