# SAG Network Live UI v1.2 — Global Map Readability

## Purpose
Improve the global operational and 3D maps without modifying the frozen SAG Network v2.0.0 runtime/core.

## Changes
- Tightly co-located local Ground/Air/User nodes are shown as a deterministic visual cluster in global and 3D views.
- The cluster label reports the runtime-derived local node total and domain counts.
- Local-local serving links are intentionally not drawn in the global/3D view because they collapse at this map scale; exact local links remain visible in the Regional view.
- Regional view continues to show the exact project coordinates and individual nodes.
- Space/orbit data remains individually rendered from project state.
- No project coordinate or backend behavior is changed by the visualization choice.

## Evidence boundary
The UI remains a visualization of software execution. It does not claim physical RF measurement, physical hardware actuation, or external-network mutation.

## Validation
- Node syntax check: PASS
- Python compile check: PASS
- `src/` unchanged from v1.1 baseline.
- `data/` unchanged from v1.1 baseline.
