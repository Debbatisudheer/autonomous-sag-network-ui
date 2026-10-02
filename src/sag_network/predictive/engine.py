from __future__ import annotations

from collections.abc import Iterable

from sag_network.predictive.features import extract_features
from sag_network.predictive.forecast import forecast_history
from sag_network.predictive.models import (
    PredictiveConfig,
    PredictiveReport,
    PredictiveThresholdRule,
)
from sag_network.predictive.risk import evaluate_early_warnings
from sag_network.telemetry.models import TelemetryRecord


class PredictiveIntelligenceEngine:
    """Deterministic predictive baseline for future network-condition estimation."""

    def __init__(self, config: PredictiveConfig | None = None) -> None:
        self.config = config or PredictiveConfig()

    def analyze(
        self,
        records: Iterable[TelemetryRecord],
        *,
        reference_time_s: float,
        rules: Iterable[PredictiveThresholdRule] = (),
    ) -> PredictiveReport:
        """Extract features, forecast future conditions, and emit threshold warnings."""
        record_list = list(records)
        features = extract_features(
            record_list,
            reference_time_s=reference_time_s,
            config=self.config,
        )
        forecasts = forecast_history(
            record_list,
            reference_time_s=reference_time_s,
            config=self.config,
        )
        warnings = evaluate_early_warnings(
            forecasts,
            reference_time_s=reference_time_s,
            rules=rules,
        )
        return PredictiveReport(
            timestamp_s=reference_time_s,
            features=features,
            forecasts=forecasts,
            early_warnings=warnings,
        )
