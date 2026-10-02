# Phase 65 — Real-World Domain Shift Detection

Status: **LOCKED — Windows and real public OPS-SAT execution validated.**

Evidence boundary: domain shift is detected without using observed anomaly labels. The detector compares a chronological reference partition (fit) against a chronological final test partition. Anomaly/label fields are ignored by the detector.

Windows final gate:
- Ruff: PASS after auto-fixing 15 inherited/project issues; final `ruff check .`: PASS.
- mypy: PASS — no issues found in 218 source files.
- pytest: PASS — 508 passed.
- Real OPS-SAT runtime: PASS.

Real public-data evidence:
- Dataset: `data/raw/opssat-ad/segments.csv`
- Evidence class: `PUBLIC DATA`
- Provenance verified: `true`
- Source SHA-256: `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`
- Rows: `303493`
- Series: `9`
- Analyzed series: `9`
- Shifted series: `6`
- Reference samples: `133483`
- Comparison samples: `44493`
- Aggregate mean shift score: `0.742887225421288`
- Aggregate max shift score: `1.0`
- Shift rate: `0.6666666666666666`
- Detection fingerprint: `5bc28d79d7ea317e05efd065c3f64cde8e2436469098683c3ab2d90e14ca6f61`
- Network mutation: `false`

Implementation:
- verified public OPS-SAT provenance and SHA-256 enforcement
- numeric and ISO-8601 timestamp support using `datetime.fromisoformat(stripped)`
- chronological fit/calibration/final-test partitioning consistent with Phases 63 and 64
- population stability index (PSI) using deterministic reference-derived histogram bins
- empirical CDF distance without external statistical dependencies
- standardized mean shift and symmetric standard-deviation ratio
- configurable detection thresholds and bounded 0-to-1 shift score
- explicit per-series detection reasons
- weighted aggregate shift score, maximum shift score, shifted-series count, and shift rate
- deterministic per-series and aggregate fingerprints
- explicit evidence-class reporting
- no network or hardware mutation

Continuity corrections carried forward before locking:
- Phase 64 `RealFailureSeries` construction remains explicitly typed; no `**dict[str, float]` ambiguity.
- Domain-shift tests use pytest `tmp_path`, not POSIX-only `/tmp/...` paths.
- Inherited ISO-8601 parser uses `datetime.fromisoformat(stripped)` directly.
