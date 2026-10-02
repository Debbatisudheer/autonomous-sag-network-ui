# Showcase v0.7 — Operational Live Map

## Purpose

v0.7 is a separate showcase layer for the frozen SAG Network v2.0.0 release. It does not replace the SAG backend under `src/`.

## Main change

The default topology surface is now an **Operational Map**. It uses a bundled static geographic basemap only for geographic context. Runtime nodes, user/resource state, serving links, handover state, and orbit points are still rendered from the actual project execution endpoints.

## Verified interfaces

- Browser home page serves correctly.
- `/world_map.png` serves the bundled basemap.
- `/api/topology?mode=synthetic&time=2400` returns 8 runtime nodes and an orbit path.
- `/api/events?mode=synthetic` executes the Phase 77 path and streams real cycle payloads.
- `/api/resilience?mode=synthetic` returns the full Phase 78 campaign: 7 scenarios, 231 cycles, 7/7 recovered, 30 handovers, 225 verification passes, 6 verification failures, 9 no-coverage, 93.51% demand satisfaction, 97.40% verification success, 25.71 s mean recovery, 180 s maximum recovery.
- Source tree under `src/` is unchanged from the v0.6 showcase package.

## Evidence boundary

`network_mutation=false`, `hardware_measurement=false`. The showcase visualizes software execution and does not claim physical RF measurement, physical hardware actuation, or external-network mutation.
