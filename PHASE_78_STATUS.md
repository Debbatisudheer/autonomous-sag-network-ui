# Phase 78 — Real-World Resilience Campaign

## Status

LOCKED — Windows final gate and resilience runtime validation completed.

## Scope

Phase 78 adds a controlled resilience campaign above the locked Phase 77 Real Closed-Loop Autonomy boundary.
The campaign repeatedly observes the common Ground-Air-Space state, injects deterministic software-side faults into
copied candidate state or the telemetry-health gate, lets the existing stateful handover controller respond, verifies
the resulting serving state, and records recovery timing and service impact.

The campaign intentionally measures resilience behavior rather than manufacturing a universal "resilient" claim.
Failure injections are simulation inputs. They do not mutate live network infrastructure, transmit RF, or actuate
physical hardware.

## Failure families

- `RESOURCE_OUTAGE`: disable one named Ground/Air/Space candidate for a bounded interval.
- `DOMAIN_OUTAGE`: disable all candidates in one network domain for a bounded interval.
- `TELEMETRY_DEGRADATION`: lower the autonomy telemetry-health gate without changing network candidate state.
- `CAPACITY_DEGRADATION`: scale the estimated capacity of selected resources to expose capacity-related verification behavior.
- `CASCADING_OUTAGE`: disable a bounded set of resources spanning multiple domains.

## Default campaign

Seven deterministic scenarios are included:

- Ground Cell 02 outage: 600–1200 s.
- UAV 01 outage: 0–120 s.
- Ground-domain isolation: 1200–1800 s.
- Air-domain isolation: 1800–2400 s.
- Telemetry-health degradation to 0.50: 600–1200 s.
- HAPS capacity collapse to 1%: 2400–3000 s.
- Full service isolation across the bundled Ground/Air/Space candidates: 2400–2700 s.

## Evidence boundary

- `SYNTHETIC FIXTURE`: deterministic Ground + Air fixtures and analytical space propagation.
- `PUBLIC EPHEMERIS`: the bundled point-in-time ISS/ZARYA NORAD 25544 TLE through SGP4.
- `PUBLIC DATA`: verified OPS-SAT replay combined with the public ephemeris path; OPS-SAT is not treated as an end-to-end SAG link measurement.
- `LOCAL NETWORK TEST`: localhost UDP telemetry transport only.

The Phase 78 fault campaign itself is a software-side resilience experiment. Public data and ephemeris are evidence inputs,
not physical failure measurements.

## Container validation

- `compileall`: pass.
- `pytest -q`: 567 passed.
- Synthetic campaign: pass.
- Ruff and mypy are not installed in the build container; Windows is authoritative for the final Ruff/mypy/pytest gate.

## Windows final gate

```powershell
ruff check . --fix
ruff check .
mypy src
pytest -q
python scripts\\run_phase78_real_world_resilience.py
python scripts\\run_phase78_real_world_resilience.py --udp-loopback
python scripts\\run_phase78_real_world_resilience.py --opssat-file data\\raw\\opssat-ad\\segments.csv --limit 16
python scripts\\run_phase78_real_world_resilience.py --real-ephemeris
```

Phase 78 is locked. Its software-side fault injection and non-ideal outcomes remain explicitly preserved as resilience evidence.
