# Phase 50 — Baseline Comparison

Phase 50 adds a deterministic forecasting-baseline comparison layer using the existing historical telemetry platform and the Phase 32 ML predictive baseline.

## Compared methods

1. Persistence baseline — repeats the latest training observation across the holdout horizon.
2. Rolling-mean baseline — repeats the mean of the configured trailing training window.
3. Phase 32 ML predictive baseline — uses the existing deterministic supervised model and recursive forecast.

## Evaluation boundary

All methods receive the same historical training prefix and are evaluated against the same future temporal holdout. The comparison reports MAE and RMSE, raw predictions, actual holdout values, and deltas relative to persistence.

## Reproducibility

The result is deterministically fingerprinted with SHA-256. No random seed, network-state mutation, external process, or external service is required.

## Evidence classification

The included Phase 50 runtime uses a synthetic offline telemetry fixture. Its numerical results demonstrate deterministic software behavior and comparative methodology; they are not real-world wireless-network measurements.
