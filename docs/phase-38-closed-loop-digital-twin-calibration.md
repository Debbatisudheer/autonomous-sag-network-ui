# Phase 38 — Closed-Loop Digital Twin Calibration

Phase 38 adds a deterministic calibration loop between observed telemetry measurements and the existing digital-twin representation.

## Scope

- Preserve the existing `DigitalTwin` snapshot/history model.
- Represent bounded calibration parameters explicitly.
- Compare observed metrics with digital-twin predictions through timestamped residual observations.
- Estimate deterministic parameter corrections using a one-step least-squares sensitivity update.
- Enforce parameter bounds and report clipping explicitly.
- Recalculate residual RMSE after the proposed calibration update.
- Produce a deterministic SHA-256 fingerprint of updated parameter values.
- Return calibrated values without mutating live `DigitalTwin` state.
- Keep offline demo data explicitly marked synthetic.

## Closed-loop boundary

```text
Observed telemetry
      ↓
Observed − twin prediction residual
      ↓
Sensitivity-weighted calibration
      ↓
Bounded parameter update
      ↓
Re-evaluate prediction residual
      ↓
Calibrated twin parameters
```

The phase is a calibration/estimation layer. It does not claim real-world deployment, automatically change network control state, or replace the underlying physics/channel models.
