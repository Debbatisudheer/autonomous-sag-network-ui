from __future__ import annotations

import json

from sag_network.domain.unified import NetworkDomain
from sag_network.predictive.engine import PredictiveIntelligenceEngine
from sag_network.predictive.models import PredictiveConfig, PredictiveThresholdRule
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _record(index: int, timestamp_s: float, value: float) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=f"sinr-{index:02d}",
        timestamp_s=timestamp_s,
        sequence=index,
        source_id="uav-a:user-01",
        domain=NetworkDomain.AIR,
        metric=TelemetryMetric.SINR_DB,
        value=value,
        unit="dB",
    )


def main() -> None:
    records = [
        _record(1, 1.0, 20.0),
        _record(2, 2.0, 17.0),
        _record(3, 3.0, 14.0),
        _record(4, 4.0, 11.0),
    ]
    engine = PredictiveIntelligenceEngine(
        PredictiveConfig(
            history_window=10,
            min_points=3,
            horizon_steps=3,
            step_s=1.0,
            max_input_age_s=5.0,
        )
    )
    report = engine.analyze(
        records,
        reference_time_s=4.0,
        rules=[
            PredictiveThresholdRule(
                source_id="uav-a:user-01",
                metric=TelemetryMetric.SINR_DB,
                minimum_value=10.0,
                warning_within_s=5.0,
                critical_within_s=2.0,
            )
        ],
    )
    latest_forecast = report.forecasts[0]
    print(
        json.dumps(
            {
                "timestamp_s": report.timestamp_s,
                "feature": {
                    "latest_value": report.features[0].latest_value,
                    "trend_per_s": report.features[0].trend_per_s,
                    "trend_r_squared": report.features[0].trend_r_squared,
                    "sample_count": report.features[0].sample_count,
                },
                "forecast": [
                    {
                        "timestamp_s": point.forecast_timestamp_s,
                        "predicted_sinr_db": point.predicted_value,
                        "confidence": point.confidence_score,
                    }
                    for point in latest_forecast.points
                ],
                "early_warnings": [
                    warning.model_dump(mode="json") for warning in report.early_warnings
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
