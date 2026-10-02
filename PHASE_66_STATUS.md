# Phase 66 — Real-World Online Model Adaptation

Status: **LOCKED — Windows and real public OPS-SAT execution validated.**

## Scope

Adds a leakage-free prequential online adaptation layer above the locked Phase 65 baseline.

## Protocol

- Fit a Phase 61-compatible ridge model on the chronological initial training partition.
- Use the final chronological stream as a holdout.
- For each stream observation, generate static and adaptive predictions before incorporating that observation.
- After the observation is observed, update a bounded recent-history buffer.
- Refit the adaptive model on the bounded history at the configured interval and when the unsupervised local shift score crosses its threshold.
- Never consume anomaly or label fields for model fitting, adaptation, or shift triggering.
- Preserve public dataset provenance and SHA-256 verification.
- Report static versus adaptive prequential metrics and deterministic fingerprints.

## Real public-data evidence

- Dataset: `data/raw/opssat-ad/segments.csv`
- Evidence class: `PUBLIC DATA`
- Provenance verified: `true`
- Source SHA-256: `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`
- Rows: `303493`
- Series: `9`
- Adapted series: `9`
- Aggregate stream samples: `44493`
- Static MAE: `0.002164392780558146`
- Adaptive MAE: `0.001930163674724015`
- Adaptation delta MAE: `-0.00023422910583413103`
- Static RMSE: `0.01316819816941141`
- Adaptive RMSE: `0.013160430572053204`
- Static R²: `0.9966984990428206`
- Adaptive R²: `0.9967023928430481`
- Scheduled updates: `886`
- Shift-triggered updates: `42346`
- Total updates: `42393`
- Adaptation fingerprint: `e96eb084498d41f01d5386f039e7fb1aa9e3ed973358dbbd5cf41231d19c06c6`
- Network mutation: `false`

These metrics are from historical replay of the verified public OPS-SAT dataset; they are not evidence of live spacecraft streaming or physical deployment. Per-series results are preserved even where adaptive error increased relative to the static model.

## Validation

Windows final gate passed:
- Ruff: PASS after auto-fixing inherited/project issues; final `ruff check .`: PASS.
- mypy: PASS — no issues found in 221 source files.
- pytest: PASS — 512 passed.
- Synthetic runtime: PASS.
- Real OPS-SAT runtime: PASS.

## Continuity

Phase 66 carries forward the Phase 65 Windows-portable tests, direct `datetime.fromisoformat(stripped)` timestamp parsing, and the corrected Phase 64 typed model construction.
