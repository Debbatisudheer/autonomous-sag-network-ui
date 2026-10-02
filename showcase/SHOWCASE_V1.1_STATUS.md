# SAG Network Live UI v1.1 — Readable Geospatial Visualization

## Purpose
Improve the showcase's geographic readability without modifying the frozen SAG Network v2.0.0 runtime/core.

## Changes
- Added collision-aware map label placement for operational, regional, and 3D globe views.
- Added leader lines for labels that must move away from tightly clustered real coordinates.
- Added domain-specific visual markers: square=Ground, triangle=Air, circle=Space/User.
- Added slight curvature to simultaneous serving links to reduce visual overlap without changing endpoints.
- Preserved actual project coordinates and runtime values.
- Preserved event-driven rendering and bounded map layout from v1.0.

## Evidence boundary
The UI remains a visualization of software execution. It does not claim physical RF measurement, physical hardware actuation, or external-network mutation.

## Validation
- Node syntax check: PASS
- Python compile check: PASS
- Real closed-loop + resilience tests: 12 passed
- /api/topology synthetic: 8 nodes, 31 orbit points
- /api/candidates synthetic: 5 candidates for a queried user/time
