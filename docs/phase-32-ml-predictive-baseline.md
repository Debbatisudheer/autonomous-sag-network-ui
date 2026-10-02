# Phase 32 — ML Predictive Baseline

Phase 32 adds the first explicitly supervised machine-learning baseline above the locked Phase 31 historical dataset platform.

## Scope

- Deterministic supervised one-step regression from historical telemetry.
- Separate model per source/metric series.
- Lagged telemetry, recent delta, and rolling-mean features.
- Chronological train/test split; no random shuffling or leakage from future samples.
- Ridge-regularized linear regression implemented with the Python standard library.
- Deterministic MAE, RMSE, and R-squared validation metrics.
- Recursive multi-step forecasting from the trained model.
- SHA-256 model fingerprints for reproducibility and provenance.
- Explicit insufficient-history state.

## Architecture

```text
Phase 31 Historical Dataset
            |
            v
     HistoricalQuery
            |
            v
    TelemetryRecord series
            |
            v
   Supervised feature builder
            |
            v
   Temporal train/test split
            |
            v
   Ridge regression baseline
            |
      +-----+-----+
      |           |
      v           v
 Validation     Model fingerprint
 metrics            |
      |             |
      +------+------+
             v
     Recursive forecast
```

## Realism boundary

The Phase 32 model is a deterministic research baseline, not a claim of production-grade ML accuracy. The bundled Phase 32 fixture is synthetic and is explicitly labeled as such. No external measurement corpus is redistributed or represented as real telemetry.

## Reproducibility

Training uses chronological samples, deterministic linear algebra, fixed regularization, and SHA-256 model fingerprints. There is no random initialization, stochastic optimizer, or hidden external service.

## Validation

Windows final gate:

```text
ruff check .
mypy src
pytest
python scripts\\run_phase32_ml_predictive_baseline.py
```
