# Showcase v0.6 correction

This package preserves the SAG Network v2.0.0 core and adds only a separate showcase layer.

## Corrected issue

The previous showcase event payload flattened topology fields (`nodes`, `orbit`, `center`, ...) while the frontend expected `p.topology`. After the first live cycle, the map therefore did not receive the topology object it expected.

v0.6 changes the event contract to carry `"topology": {...}` on each cycle and also includes an initial topology object in the SSE `start` event.

The frontend now also calls `/api/topology` on page load and when the demo mode changes, so the actual project fixture state is visible before the first cycle.

## Core integrity

No files under `src/` are changed by the showcase work. The included `src/` tree is the v2.0.0 release tree copied into this separate showcase package for runtime use.
