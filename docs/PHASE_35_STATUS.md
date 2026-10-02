# Phase 35 — Predictive Failure Intelligence

Status: implementation complete; Windows validation required before lock.

Phase 35 converts calibrated Phase 34 prediction intervals into deterministic failure-risk findings using explicit, scenario-owned threshold rules. It does not mutate network state or execute recovery actions.

## Added

- Explicit failure threshold rules per telemetry metric/source.
- Deterministic threshold-crossing detection using Phase 34 lower/upper prediction bounds.
- Watch/warning/critical lead-time classification.
- Bounded heuristic risk score that combines threshold proximity and uncertainty score.
- Stable SHA-256 event identifiers.
- Deterministic ordering of findings and rules.
- Explicit `state_mutation: False` runtime validation.
- Phase 35 tests and synthetic runtime fixture.

## Validation in build environment

- `pytest`: 369 passed.
- `compileall`: passed.
- Phase 35 runtime: pass, 3 predicted failure conditions.

The runtime fixture is synthetic. Risk scores are deterministic heuristic scores, not calibrated probabilities.

## Windows gate

Run `ruff check .`, `mypy src`, `pytest`, and `python scripts\\run_phase35_predictive_failure_intelligence.py` before locking the phase.
