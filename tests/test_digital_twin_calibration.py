from __future__ import annotations

import pytest

from sag_network.digital_twin.calibration import (
    CalibrationObservation,
    CalibrationParameter,
    DigitalTwinCalibrator,
)


def parameter(*, value: float = 1.0) -> CalibrationParameter:
    return CalibrationParameter(
        name="path_loss_bias_db",
        value=value,
        lower_bound=-5.0,
        upper_bound=5.0,
        learning_rate=1.0,
    )


def observations() -> list[CalibrationObservation]:
    return [
        CalibrationObservation(
            timestamp_s=1.0,
            parameter_name="path_loss_bias_db",
            metric_name="sinr_db",
            observed_value=8.0,
            predicted_value=6.0,
            sensitivity=1.0,
        ),
        CalibrationObservation(
            timestamp_s=2.0,
            parameter_name="path_loss_bias_db",
            metric_name="sinr_db",
            observed_value=10.0,
            predicted_value=8.0,
            sensitivity=1.0,
        ),
    ]


def test_calibration_reduces_residual_error() -> None:
    report = DigitalTwinCalibrator().calibrate([parameter()], observations())
    result = report.calibrated_parameters[0]
    assert result.updated_value == pytest.approx(3.0)
    assert result.adjustment == pytest.approx(2.0)
    assert result.rmse_before == pytest.approx(2.0)
    assert result.rmse_after == pytest.approx(0.0)
    assert report.rmse_after < report.rmse_before
    assert report.state_mutation is False


def test_calibration_is_deterministic() -> None:
    engine = DigitalTwinCalibrator()
    first = engine.calibrate([parameter()], observations())
    second = engine.calibrate([parameter()], observations())
    assert first == second


def test_bounds_are_enforced() -> None:
    report = DigitalTwinCalibrator().calibrate(
        [parameter(value=4.0)],
        [
            CalibrationObservation(
                timestamp_s=1.0,
                parameter_name="path_loss_bias_db",
                metric_name="sinr_db",
                observed_value=20.0,
                predicted_value=0.0,
                sensitivity=1.0,
            )
        ],
    )
    result = report.calibrated_parameters[0]
    assert result.updated_value == 5.0
    assert result.clipped is True


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown parameters"):
        DigitalTwinCalibrator().calibrate(
            [parameter()],
            [
                CalibrationObservation(
                    timestamp_s=1.0,
                    parameter_name="unknown",
                    metric_name="sinr_db",
                    observed_value=1.0,
                    predicted_value=0.0,
                    sensitivity=1.0,
                )
            ],
        )


def test_empty_observations_leave_parameters_unchanged() -> None:
    report = DigitalTwinCalibrator().calibrate([parameter()], [])
    result = report.calibrated_parameters[0]
    assert result.updated_value == 1.0
    assert result.sample_count == 0
    assert report.rmse_before == 0.0
    assert report.rmse_after == 0.0
