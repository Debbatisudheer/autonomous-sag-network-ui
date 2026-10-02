# Phase 33 — Time-Series Deep Learning

Phase 33 adds a deterministic sequence-to-one neural forecasting layer on top of the locked Phase 32 ML predictive baseline.

## Scope

- Fixed-length lag windows from historical telemetry.
- Deterministic feature standardization using the training split only.
- Single-hidden-layer tanh neural network trained by full-batch gradient descent.
- Chronological train/test holdout; no future samples are used during training.
- Deterministic seed, training configuration, model fingerprint, and recursive multi-step forecasts.
- Per-source/per-metric model isolation.
- Explicit insufficient-history state.
- Training and validation metrics: MAE, RMSE, R², and train MSE.
- Synthetic validation fixture clearly identified as synthetic.

## Architecture

```text
Phase 31 Historical Dataset
          |
          v
  TelemetryRecord history
          |
          v
   Lag-window builder
          |
          v
 Training-only normalization
          |
          v
  Temporal train/test split
          |
          v
 Deterministic neural model
  tanh hidden layer + GD
          |
       +--+--+
       |     |
       v     v
 Validation  Model fingerprint
 metrics          |
       +-----+----+
             v
    Recursive forecast
```

## Validation

Windows validation is the authoritative release gate:

```powershell
ruff check .
mypy src
pytest
python scripts\run_phase33_time_series_deep_learning.py
```

Phase 33 is not locked until all four gates pass on the Windows development environment.
