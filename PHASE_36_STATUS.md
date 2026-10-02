# Phase 36 — Learned Decision Engine

Status: IMPLEMENTED; Windows final validation pending.

Phase 36 adds a deterministic supervised learned-value model above the validated Phase 18 decision policy. It trains only from explicit action/outcome examples, uses ridge regression with a deterministic solver, and re-ranks actions already checked for feasibility by the existing policy layer.

The offline runtime fixture is synthetic and explicitly labeled as such. No network state is mutated and no control command is executed.

## Validation target

- Ruff: all checks passed.
- mypy: no issues.
- pytest: full suite passed.
- Runtime: `python scripts\\run_phase36_learned_decision_engine.py` status `pass`.

Phase 36 must remain unlocked until the Windows final gate is clean.
