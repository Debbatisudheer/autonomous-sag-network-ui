# SAG Network Live UI v0.9

## Purpose
Fix the topology map vertical-growth/rendering issue without changing the SAG v2.0.0 backend/source tree.

## Fixes
- Fixed the topology viewport to a bounded 620px desktop height.
- Fixed the map canvas to a bounded 542px desktop drawing area.
- Fixed the mobile viewport to a bounded 520px panel / 442px canvas.
- Updated canvas resize logic to avoid rewriting canvas pixel dimensions every animation frame unless the size actually changes.
- Preserved the actual `src/` and `data/` trees from the v0.8 showcase baseline.

## Evidence boundary
The showcase remains a visualization layer over the existing deterministic project execution. It does not claim physical RF measurement, physical hardware actuation, or external-network mutation.
