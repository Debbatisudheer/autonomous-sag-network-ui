# Phase 9 — Unified Space-Air-Ground Network

## Scope

Phase 9 composes the already validated Ground, Air, and Space domains into one common network state. It does not replace the underlying physical models or domain-specific association logic.

## Common candidate model

Every user-to-resource observation is exposed through the same schema:

- domain
- resource identifier/type
- availability
- distance
- received power
- noise
- SINR
- link margin
- Shannon capacity
- estimated schedulable capacity
- propagation delay
- optional Doppler
- optional aerial energy state
- optional predicted satellite loss time

## Baseline policy

The baseline is deterministic and non-AI. It evaluates all feasible Ground, Air, and Space candidates together and uses a load-aware shared-rate calculation. Tie-breaking remains deterministic.

This baseline is important because later predictive and AI policies must be compared against a known reference.

## Modeling boundary

The unified layer does not invent a new physical channel. It consumes the existing validated link models:

- Ground: WGS84 geometry + configured link budget
- Air: WGS84 geometry + configured link budget + deterministic energy model
- Space: orbital propagation + visibility + Doppler + NTN link budget

The unified candidate schema is an orchestration boundary, not a claim of a commercial 5G/NTN implementation.

## Next phase

Phase 10 will add multi-domain connectivity continuity and explicit cross-domain handover behavior so a user can transition between Ground, Air, and Space resources under one controller.
