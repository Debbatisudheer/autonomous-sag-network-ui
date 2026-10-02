# Phase 79 — Autonomous SAG Validation

## Status

LOCKED — Windows final gate passed after the typed Pydantic fingerprint correction.

## Scope

Phase 79 is the validation/consolidation layer above the locked Phase 76 Cross-Domain SAG Network,
Phase 77 Real Closed-Loop Autonomy, and Phase 78 Real-World Resilience Campaign.

It does not replace or rebuild any predecessor phase. It reruns their existing engines and validates:

- cross-domain user/candidate population and coverage;
- autonomous demand satisfaction and post-action verification;
- resilience scenario recovery and retention of non-ideal outcomes;
- deterministic repeatability through repeated integration fingerprints;
- provenance requirements for public-data runs;
- evidence boundaries so software/synthetic/public inputs are not mislabeled as physical deployment evidence;
- absence of external network mutation and physical hardware measurement claims.

## Evidence boundary

- `SYNTHETIC FIXTURE`: deterministic Ground + Air fixtures and analytical space propagation.
- `PUBLIC EPHEMERIS`: bundled point-in-time ISS/ZARYA NORAD 25544 TLE through SGP4.
- `PUBLIC DATA`: verified OPS-SAT replay plus the public SGP4 path; OPS-SAT is not treated as a measured end-to-end SAG link.
- `LOCAL NETWORK TEST`: localhost UDP telemetry transport only.

Phase 79 itself is a software/research validation layer. It does not claim deployment of a physical SAG network.

## Latest correction

The Phase 79 validation fingerprint helper now accepts `pydantic.BaseModel` reports and calls the typed `model_dump(mode="json")` API directly. This resolves the Windows mypy error where an untyped `object` was inferred to have no `model_dump` attribute. No validation behavior or evidence semantics were changed.

## Container validation

- `pytest -q`: expected to include all inherited tests plus Phase 79 tests.
- `compileall`: required before packaging.
- Ruff and mypy are not assumed available in the build container; Windows is authoritative for the final gate.

## Windows final gate

```powershell
ruff check . --fix
ruff check .
mypy src
pytest -q
python scripts\run_phase79_autonomous_sag_validation.py
python scripts\run_phase79_autonomous_sag_validation.py --udp-loopback
python scripts\run_phase79_autonomous_sag_validation.py --opssat-file data\raw\opssat-ad\segments.csv --limit 16
python scripts\run_phase79_autonomous_sag_validation.py --real-ephemeris
```

Phase 79 is locked. The consolidated validation preserves the Phase 78 resilience imperfections and keeps all evidence classes explicitly separated.
