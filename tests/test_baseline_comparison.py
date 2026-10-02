from __future__ import annotations

import pytest

from sag_network.baseline_comparison import (
    BaselineComparisonConfig,
    BaselineComparisonRunner,
    BaselineMethod,
)
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def history(values: list[float]) -> list[TelemetryRecord]:
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
        )
        for index, value in enumerate(values, start=1)
    ]


def test_phase50_compares_three_deterministic_methods() -> None:
    result = BaselineComparisonRunner().run(
        history([20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]),
        experiment_id="test-phase50",
        config=BaselineComparisonConfig(holdout_size=5),
        fixture="synthetic test fixture",
    )
    assert result.training_count == 15
    assert result.holdout_count == 5
    assert [item.method for item in result.metric_results] == [
        BaselineMethod.PERSISTENCE,
        BaselineMethod.ROLLING_MEAN,
        BaselineMethod.ML_PREDICTIVE_BASELINE,
    ]
    assert len(result.comparisons) == 2
    assert len(result.result_fingerprint) == 64


def test_phase50_is_deterministic() -> None:
    records = history([30.0, 29.0, 28.0, 27.0, 26.0, 25.0, 24.0, 23.0, 22.0, 21.0, 20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0])
    runner = BaselineComparisonRunner()
    first = runner.run(records, experiment_id="deterministic", fixture="synthetic")
    second = runner.run(records, experiment_id="deterministic", fixture="synthetic")
    assert first == second


def test_phase50_rejects_mixed_series() -> None:
    records = history([1.0] * 20)
    records.append(
        records[-1].model_copy(
            update={
                "record_id": "other",
                "source_id": "other-source",
                "sequence": 21,
                "timestamp_s": 21.0,
            }
        )
    )
    with pytest.raises(ValueError, match="exactly one source/metric series"):
        BaselineComparisonRunner().run(records, experiment_id="mixed", fixture="synthetic")


def test_phase50_rejects_insufficient_history() -> None:
    with pytest.raises(ValueError, match="enough training samples"):
        BaselineComparisonRunner().run(
            history([1.0] * 12),
            experiment_id="short",
            config=BaselineComparisonConfig(minimum_training_samples=10, holdout_size=5),
            fixture="synthetic",
        )
