from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from sag_network.real_training import RealDataModelTrainer, RealDataTrainingConfig
from sag_network.real_training.models import TrainingEvidence


def _dataset(path: Path, *, manifest: bool = False) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "channel", "value", "train"])
        for index in range(50):
            writer.writerow([index, "ch-a", 30.0 - index * 0.4, 1])
    if manifest:
        import hashlib

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(path.suffix + ".manifest.json").write_text(
            json.dumps({"sha256": digest, "verified": True}), encoding="utf-8"
        )


def test_trains_deterministically_from_fixture(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    _dataset(dataset)
    trainer = RealDataModelTrainer()
    config = RealDataTrainingConfig(minimum_samples=20)
    first = trainer.train_csv(dataset, config=config, evidence_class=TrainingEvidence.SYNTHETIC_FIXTURE)
    second = trainer.train_csv(dataset, config=config, evidence_class=TrainingEvidence.SYNTHETIC_FIXTURE)
    assert first.training_fingerprint == second.training_fingerprint
    assert first.trained_series_count == 1
    assert first.results[0].test_samples > 0


def test_public_data_requires_verified_manifest(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    _dataset(dataset)
    with pytest.raises(ValueError, match="verified provenance"):
        RealDataModelTrainer().train_csv(dataset)


def test_public_manifest_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    dataset = tmp_path / "segments.csv"
    _dataset(dataset, manifest=True)
    manifest = dataset.with_suffix(dataset.suffix + ".manifest.json")
    manifest.write_text(json.dumps({"sha256": "0" * 64, "verified": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        RealDataModelTrainer().train_csv(dataset)
