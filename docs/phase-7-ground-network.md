# Phase 7 — Terrestrial Ground Network and Multi-User State

## Purpose

Phase 7 introduces a deterministic terrestrial baseline so the project no longer models the space segment in isolation.

## Scope

- WGS84 ground-cell and user positions
- Terrestrial radio link budget using the validated shared link-budget functions
- Explicit service-radius constraint
- Multi-user association
- Deterministic load-aware greedy association
- Equal-share scheduling ceiling with configurable efficiency
- Per-user candidate and association state

## Modeling boundary

This phase is an engineering baseline, not a full 3GPP terrestrial channel implementation. The current ground link uses geometric distance plus free-space path loss and explicit configured losses. It does **not** yet model terrain, buildings, shadowing, multipath, fast fading, antenna patterns, beamforming, detailed 3GPP channel models, scheduler-specific PHY/MAC behavior, or real operator topology.

The `estimated_capacity_bps` value is an analytical scheduling ceiling derived from Shannon capacity multiplied by a configured efficiency factor. It is not presented as measured application throughput.

Those limitations are deliberate. Later phases can replace individual models behind interfaces without changing the rest of the architecture.

## Why this phase matters

The autonomous system eventually needs to choose among multiple network domains. A terrestrial baseline gives us a second real candidate type to place beside the existing NTN candidates. Future orchestration can then compare ground and non-terrestrial options using the same timestamped network state.
