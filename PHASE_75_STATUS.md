# Phase 75 — Space Segment Data Integration

## Status

LOCKED after Windows validation on 2026-10-01.

## Windows validation

- Ruff: all checks passed after `ruff check . --fix` reported 32 auto-fixes.
- mypy: no issues found in 251 source files.
- pytest: 549 passed in 65.49s.
- Synthetic integration: PASS.
- Localhost UDP integration: PASS; 16/16 records delivered, ~1.254 ms loopback latency.
- Public OPS-SAT replay: PASS; provenance verified against source SHA-256 `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`.
- Public SGP4 ephemeris run: PASS using the bundled point-in-time ISS (ZARYA), NORAD 25544 TLE through the project SGP4 backend.

## Scope

Phase 75 integrates the canonical telemetry loop with the existing satellite visibility and NTN link model. The implementation supports the bundled public ISS (ZARYA), NORAD 25544 TLE through the existing SGP4 backend when the project `sgp4` dependency is installed.

## Evidence classes

- `SYNTHETIC FIXTURE`: deterministic analytical two-body satellite integration with the bundled TLE-derived orbital elements.
- `PUBLIC EPHEMERIS`: SGP4 propagation using the bundled point-in-time ISS (ZARYA) TLE sourced from the CelesTrak public GP endpoint recorded in `data/ephemeris/README.md`.
- `PUBLIC DATA`: verified OPS-SAT OPSSAT-AD telemetry replay combined with the public ISS ephemeris fixture. OPS-SAT timestamps are normalized to elapsed replay time for integration with the independent ISS ephemeris clock. This does not claim that OPS-SAT telemetry belongs to ISS or represents a measured satellite link.
- `LOCAL NETWORK TEST`: localhost UDP telemetry transport only.

## Observed public-data behavior

For the tested reference timestamp, the ISS candidate was below the configured visibility threshold for all three deterministic Hyderabad-area users, so 0 users were associated and 3 were unassociated. This is retained as observed output; the public OPS-SAT replay is not treated as measured satellite-link evidence.

## Outputs

The report contains satellite/user candidate states, visibility-derived availability, link margin, elevation, propagation delay, Doppler shift, allocated capacity, telemetry-loop state count, propagation model, ephemeris source, and deterministic integration fingerprints.

## Hardware boundary

No RF hardware is invoked by Phase 75. Physical SDR and RF measurements remain Phase 67–69/72 boundaries.

## Next phase

Phase 76 — Cross-Domain SAG Network.
