# Phase 61 — Real-Data Model Training

Status: LOCKED — validated on Windows with the verified public ESA/KP Labs OPSSAT-AD v2 `segments.csv` dataset.

Evidence boundary: the default demo is a synthetic fixture. The `--opssat-file` path trains only from the verified public OPS-SAT dataset and requires its provenance manifest to match the dataset SHA-256.

Final Windows validation:
- Ruff: clean
- mypy: no issues in 206 source files
- pytest: 491 passed
- real public OPS-SAT run: pass
- provenance: verified
- network mutation: false

Real-data evidence:
- 303,493 source rows
- 9 telemetry series trained
- source SHA-256: `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`
- training fingerprint: `9951c160736cffa02ace9954311c4106cbe1a0181a9d21dd8f03cc14ebd9173c`

Implementation:
- deterministic next-step ridge regression
- per-channel time-series grouping
- chronological holdout using the dataset `train` flag
- deterministic chronological ordering
- MAE, RMSE, and R-squared evaluation
- model fingerprints
- dataset SHA-256 and provenance verification
- explicit evidence classification
- numeric and ISO-8601 timestamp support
- no network or hardware mutation
