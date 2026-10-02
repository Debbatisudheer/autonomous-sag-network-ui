# Phase 15 — Digital Twin

## Scope

Phase 15 establishes a deterministic, versioned digital representation of the existing
Ground-Air-Space network. It consumes validated state from Phases 1–14 instead of replacing or
reimplementing their physical models.

The digital twin provides:

- synchronized snapshots of unified network state;
- optional end-to-end topology state;
- optional spectrum scheduling state;
- optional interference evaluations;
- deterministic SHA-256 state hashing for reproducibility and integrity checks;
- bounded in-memory snapshot history;
- monotonic simulation-time enforcement;
- snapshot identity and network-identity validation;
- historical lookup at or before a requested simulation time;
- deterministic state-delta detection across users, candidates, topology, spectrum, and
  interference;
- explicit synchronization boundaries between the unified state and spectrum state timestamps.

## Architecture boundary

The twin is a state mirror and scenario-state container. It does not independently calculate orbit
propagation, RF link budgets, mobility, routing, QoS, resource allocation, interference, or channel
physics. Those remain owned by the previously validated domain layers.

The intended later loop is:

`Observe -> synchronize twin -> simulate/forecast -> decide -> coordinate -> act -> verify`

Phase 16 will provide the telemetry and real-time state-ingestion layer that feeds the twin over
continuous time. Phase 17 will add predictive intelligence on top of synchronized twin history.

## Snapshot integrity

Every snapshot carries a SHA-256 hash over its canonical JSON content excluding the hash itself.
The twin verifies the hash before accepting a snapshot. This gives deterministic detection of
accidental or unauthorized state mutation within the software testbed.

Snapshots are bound to one configured network name and must use the same timestamp as their unified
state and spectrum scheduling state. Snapshot IDs are unique within the retained history.

## Delta model

A `TwinDelta` does not invent a statistical estimate. It reports deterministic structural changes
between two validated snapshots, including changed user associations, resource candidates, topology
nodes, topology links, spectrum utilization resources, and interference evaluations.

## Realism boundary

This phase is an engineering digital-twin state layer, not a claim of a live production digital twin
connected to physical 5G, 6G, UAV, HAPS, or LEO infrastructure. External telemetry, real
  ephemerides,
SDR measurements, terrain data, and live network interfaces remain future integration points.

## Validation

Phase 15 tests cover:

- deterministic state hashing;
- tamper detection;
- timestamp ordering;
- history retention and lookup;
- deterministic state deltas;
- topology and spectrum change detection;
- synchronized timestamp validation;
- duplicate snapshot protection;
- network-identity protection;
- operation with optional topology/spectrum/interference components.
