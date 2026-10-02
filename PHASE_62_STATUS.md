# Phase 62 — Real-Data Baseline Comparison

Status: LOCKED — validated on Windows with the verified public ESA/KP Labs OPSSAT-AD v2 `segments.csv` dataset.

Evidence boundary: this phase compares deterministic next-step forecasting methods on the verified public OPS-SAT telemetry dataset. It does not claim live spacecraft telemetry, physical network measurements, or universal model superiority beyond the measured holdout population and protocol.

Final Windows validation:
- Ruff: clean
- mypy: no issues in 209 source files
- pytest: 494 passed
- real public OPS-SAT run: pass
- provenance: verified
- network mutation: false

Real-data evidence:
- 303,493 source rows
- 9 telemetry series compared
- aggregate persistence MAE: `0.09190899215724992`
- aggregate rolling-mean MAE: `0.09189668981381162`
- aggregate Phase 61 ridge MAE: `0.002164392780558146`
- comparison fingerprint: `ad7b5947d5ddf946a76917e469cfc014938a097bc0a4232f52edb5c91695cf98`
- source SHA-256: `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`

Implementation:
- verified public OPS-SAT provenance and SHA-256 enforcement
- chronological per-channel holdout matching Phase 61
- persistence baseline
- rolling-mean baseline
- deterministic Phase 61 ridge-model reproduction
- MAE, RMSE, and R-squared per series and aggregate
- deterministic comparison fingerprint
- numeric and ISO-8601 timestamp support
- no network or hardware mutation
