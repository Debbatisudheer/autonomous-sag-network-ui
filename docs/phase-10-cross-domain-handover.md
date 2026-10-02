# Phase 10 — Cross-Domain Connectivity and Handover

## Goal

Provide a deterministic baseline controller that can keep a user's serving resource stable while the user's best available resource moves between Ground, Air, and Space.

## What this phase adds

- A domain-neutral handover event model.
- Hysteresis to suppress small oscillations.
- Time-to-trigger to require a candidate to remain better before switching.
- Immediate replacement when the serving resource becomes unavailable.
- Explicit `ATTACH`, `RETAIN`, `HANDOVER`, and `NO_COVERAGE` states.
- A small orchestration helper for one stateful controller per user.

## Boundary

This phase is a network-control baseline, not a full 3GPP inter-RAT handover implementation. It does not claim to execute bearer transfer, session continuity, authentication, radio signaling, or core-network procedures. Those can be added later behind explicit interfaces.

The controller consumes measurements already produced by the Ground, Air, and Space models. It does not invent RF or mobility measurements.
