# Phase 63 — Real-World Uncertainty Calibration

Status: **LOCKED — validated on Windows with the verified public OPS-SAT dataset.**

Evidence class: **PUBLIC DATA**.

Windows validation:
- `ruff check . --fix` completed with 12 fixes and 0 remaining errors
- `ruff check .` passed
- `mypy src` passed with no issues in 212 source files
- `pytest -q` passed: 498 tests
- real OPS-SAT execution passed
- `network_mutation`: false

Dataset evidence:
- source: ESA/KP Labs OPSSAT-AD v2 `segments.csv`
- rows: 303,493
- series: 9
- calibrated series: 9
- SHA-256: `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`
- provenance verified: true

Calibration configuration:
- confidence level: 0.90
- method: split conformal absolute residuals
- chronological fit/calibration/final-test partitions
- Phase 61-compatible ridge point model

Real-data aggregate result:
- final test samples: 44,493
- empirical coverage: 0.9168858022610298
- coverage gap: +0.01688580226102976
- mean interval width: 0.009197100031352943
- calibration residual MAE: 0.0021114900812215036
- calibration fingerprint: `4e19d4ebe7df6a12ac72a4b44fc2a5e2038f5fc11b7585dd182c79c48f25dd02`

Important interpretation boundary:
- 6 of 9 series met or exceeded the 0.90 empirical test-coverage target.
- CADC0886, CADC0890, and CADC0894 were below that target on their respective final holdouts.
- These are measured dataset/protocol outcomes, not a claim that the calibration is universally valid under arbitrary future distribution shift.
- The below-target series are retained as real evidence for later robustness and failure-intelligence work.

Continuity correction:
- The Phase 62 inherited ISO-8601 parser fix is carried forward: `datetime.fromisoformat(stripped)`.
