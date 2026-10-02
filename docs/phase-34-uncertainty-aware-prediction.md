# Phase 34 — Uncertainty-Aware Prediction

Phase 34 extends the locked Phase 33 time-series deep-learning predictor with deterministic uncertainty calibration.

## Design

```text
Phase 33 Point Forecast
          |
          v
Chronological Holdout Residuals
          |
          v
Empirical Conformal Quantile
          |
          +----> Confidence Level
          |
          v
Horizon Growth Adjustment
          |
          v
Lower / Point / Upper Forecast
          |
          v
Normalized Uncertainty Score
```

## Guarantees

- Calibration uses the same chronological holdout concept as Phase 33.
- Residuals are sorted deterministically before quantile selection.
- Confidence level is explicit and configurable.
- Forecast intervals widen deterministically with horizon when configured.
- Insufficient history and insufficient calibration are explicit states.
- Model fingerprints remain tied to the Phase 33 point-forecast model.
- The implementation does not claim that synthetic-fixture coverage represents real-world statistical coverage.

## Runtime fixture

The validation fixture is synthetic historical telemetry and is explicitly labeled as such.
