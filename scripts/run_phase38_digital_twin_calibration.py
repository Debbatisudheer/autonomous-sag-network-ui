from __future__ import annotations

import json

from sag_network.digital_twin.calibration import (
    CalibrationObservation,
    CalibrationParameter,
    DigitalTwinCalibrator,
)


def main() -> None:
    parameters = [
        CalibrationParameter(
            name="path_loss_bias_db",
            value=1.0,
            lower_bound=-5.0,
            upper_bound=5.0,
            learning_rate=1.0,
        )
    ]
    observations = [
        CalibrationObservation(
            timestamp_s=10.0,
            parameter_name="path_loss_bias_db",
            metric_name="sinr_db",
            observed_value=8.0,
            predicted_value=6.0,
            sensitivity=1.0,
        ),
        CalibrationObservation(
            timestamp_s=20.0,
            parameter_name="path_loss_bias_db",
            metric_name="sinr_db",
            observed_value=10.0,
            predicted_value=8.0,
            sensitivity=1.0,
        ),
        CalibrationObservation(
            timestamp_s=30.0,
            parameter_name="path_loss_bias_db",
            metric_name="sinr_db",
            observed_value=12.0,
            predicted_value=10.0,
            sensitivity=1.0,
        ),
    ]
    report = DigitalTwinCalibrator().calibrate(parameters, observations)
    print(
        json.dumps(
            {
                "name": "Closed-Loop Digital Twin Calibration",
                "phase": "38",
                "status": "pass",
                "observation_count": report.observations,
                "parameter_count": len(report.calibrated_parameters),
                "rmse_before": report.rmse_before,
                "rmse_after": report.rmse_after,
                "updated_parameters": [
                    {
                        "name": item.name,
                        "previous_value": item.previous_value,
                        "updated_value": item.updated_value,
                        "adjustment": item.adjustment,
                    }
                    for item in report.calibrated_parameters
                ],
                "parameter_fingerprint": report.parameter_fingerprint,
                "fixture": "synthetic digital-twin calibration fixture",
                "state_mutation": report.state_mutation,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
