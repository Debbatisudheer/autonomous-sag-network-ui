# Phase 64 — Real Failure Intelligence

Status: **LOCKED — Windows and real public OPS-SAT execution validated.**

Evidence boundary: predictive anomaly/failure-risk intelligence is derived from real telemetry. The model is fit without observed anomaly labels. The `anomaly`/`label` fields are used only for held-out post-hoc evaluation of risk signals; they are not used to fit the predictive model.

Implementation:
- verified public OPS-SAT provenance and SHA-256 enforcement
- numeric and ISO-8601 timestamp support
- chronological fit/calibration/final-test partitioning
- Phase 61-compatible ridge forecasting
- split-conformal absolute residual scale from calibration data
- fit-partition normal operating envelope using configurable lower/upper quantiles
- deterministic predictive risk score from forecast excursion beyond the normal envelope, normalized by conformal residual scale
- held-out anomaly-label evaluation with no label leakage into training
- precision, recall, F1, false positives, false negatives, and risk-score statistics
- deterministic per-series and aggregate fingerprints
- explicit evidence-class reporting
- no network or hardware mutation

Default configuration:
- confidence level: 0.90
- lag steps: 3
- calibration fraction: 0.20
- final test fraction: 0.20
- minimum calibration samples: 20
- normal operating envelope: 1st to 99th empirical percentile of the fit partition
- maximum rows per series: 50,000

Windows final gate required before locking:
- `ruff check . --fix`
- `ruff check .`
- `mypy src`
- `pytest -q`
- `python scripts\\run_phase64_real_failure_intelligence.py`
- real dataset run: `python scripts\\run_phase64_real_failure_intelligence.py --opssat-file data\\raw\\opssat-ad\\segments.csv`

Important interpretation boundary:
- This phase reports predictive-risk signals against the dataset's observed anomaly labels.
- An `anomaly` label is not assumed to mean a physical spacecraft failure without supporting dataset semantics.
- Real physical failure prediction, live telemetry, SDR, and hardware validation remain later phases.
