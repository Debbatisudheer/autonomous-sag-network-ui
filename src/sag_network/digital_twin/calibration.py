from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict

from pydantic import BaseModel, Field, model_validator


class CalibrationParameter(BaseModel):
    """One bounded digital-twin parameter eligible for deterministic calibration."""

    name: str = Field(min_length=1)
    value: float
    lower_bound: float
    upper_bound: float
    learning_rate: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> CalibrationParameter:
        if self.lower_bound > self.upper_bound:
            raise ValueError("lower_bound must not exceed upper_bound")
        if not self.lower_bound <= self.value <= self.upper_bound:
            raise ValueError("value must be within calibration bounds")
        return self


class CalibrationObservation(BaseModel):
    """One observed-versus-twin prediction residual used for calibration."""

    timestamp_s: float = Field(ge=0)
    parameter_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    observed_value: float
    predicted_value: float
    sensitivity: float


class CalibratedParameter(BaseModel):
    """Result for one calibrated parameter."""

    name: str = Field(min_length=1)
    previous_value: float
    updated_value: float
    adjustment: float
    lower_bound: float
    upper_bound: float
    sample_count: int = Field(ge=0)
    rmse_before: float = Field(ge=0)
    rmse_after: float = Field(ge=0)
    clipped: bool = False


class CalibrationReport(BaseModel):
    """Deterministic closed-loop calibration result without live-state mutation."""

    observations: int = Field(ge=0)
    calibrated_parameters: list[CalibratedParameter] = Field(default_factory=list)
    rmse_before: float = Field(ge=0)
    rmse_after: float = Field(ge=0)
    parameter_fingerprint: str = Field(min_length=64, max_length=64)
    state_mutation: bool = False


class DigitalTwinCalibrator:
    """Estimate bounded twin-parameter corrections from observed residuals.

    The estimator uses a deterministic one-step least-squares gradient update. It
    returns new parameter values rather than changing a live DigitalTwin snapshot.
    """

    def __init__(self, *, regularization: float = 0.0) -> None:
        if regularization < 0:
            raise ValueError("regularization must be non-negative")
        self.regularization = regularization

    def calibrate(
        self,
        parameters: list[CalibrationParameter],
        observations: list[CalibrationObservation],
    ) -> CalibrationReport:
        parameter_map = {parameter.name: parameter for parameter in parameters}
        if len(parameter_map) != len(parameters):
            raise ValueError("calibration parameter names must be unique")
        unknown = sorted({item.parameter_name for item in observations} - set(parameter_map))
        if unknown:
            raise ValueError(f"observations reference unknown parameters: {unknown}")

        grouped: dict[str, list[CalibrationObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.parameter_name].append(observation)

        results: list[CalibratedParameter] = []
        all_before: list[float] = []
        all_after: list[float] = []

        for name in sorted(parameter_map):
            parameter = parameter_map[name]
            samples = sorted(
                grouped.get(name, []),
                key=lambda item: (item.timestamp_s, item.metric_name, item.observed_value),
            )
            residuals = [item.observed_value - item.predicted_value for item in samples]
            before_sq = [residual * residual for residual in residuals]
            numerator = sum(
                item.sensitivity * (item.observed_value - item.predicted_value)
                for item in samples
            )
            denominator = sum(item.sensitivity * item.sensitivity for item in samples)
            raw_step = (
                parameter.learning_rate * numerator / (denominator + self.regularization)
                if samples and denominator + self.regularization > 0
                else 0.0
            )
            proposed = parameter.value + raw_step
            updated = min(max(proposed, parameter.lower_bound), parameter.upper_bound)
            adjustment = updated - parameter.value
            clipped = updated != proposed

            after_residuals = [
                (item.observed_value - (item.predicted_value + item.sensitivity * adjustment))
                for item in samples
            ]
            after_sq = [residual * residual for residual in after_residuals]
            all_before.extend(before_sq)
            all_after.extend(after_sq)
            results.append(
                CalibratedParameter(
                    name=name,
                    previous_value=parameter.value,
                    updated_value=updated,
                    adjustment=adjustment,
                    lower_bound=parameter.lower_bound,
                    upper_bound=parameter.upper_bound,
                    sample_count=len(samples),
                    rmse_before=_rmse(before_sq),
                    rmse_after=_rmse(after_sq),
                    clipped=clipped,
                )
            )

        fingerprint_payload = {
            item.name: item.updated_value
            for item in results
        }
        encoded = json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return CalibrationReport(
            observations=len(observations),
            calibrated_parameters=results,
            rmse_before=_rmse(all_before),
            rmse_after=_rmse(all_after),
            parameter_fingerprint=hashlib.sha256(encoded).hexdigest(),
        )


def _rmse(squared_errors: list[float]) -> float:
    if not squared_errors:
        return 0.0
    total: float = sum(squared_errors)
    mean: float = total / float(len(squared_errors))
    return math.sqrt(mean)


__all__ = [
    "CalibratedParameter",
    "CalibrationObservation",
    "CalibrationParameter",
    "CalibrationReport",
    "DigitalTwinCalibrator",
]
