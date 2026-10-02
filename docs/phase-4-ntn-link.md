# Phase 4 — NTN Link Model

## Scope

Phase 4 turns the satellite link from a free-space-only calculation into a transparent, configurable link-budget and link-state model.

## Added

- Explicit atmospheric, rain, polarization, and implementation-loss inputs.
- Total path loss = free-space path loss + explicit additional losses.
- Receiver thermal noise from bandwidth, temperature, and noise figure.
- Optional interference power.
- SINR and required-SINR link margin.
- Shannon capacity upper bound.
- `available` requires geometric visibility and non-negative SINR margin.

## Modeling boundary

Loss values are scenario inputs, not claimed measurements. The Shannon result is an idealized upper bound, not a promise of application throughput. Later phases can replace scenario loss inputs with time/location/frequency-specific propagation models and add PHY/MAC efficiency factors.
