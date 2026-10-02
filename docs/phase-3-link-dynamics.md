# Phase 3 — Satellite Link Dynamics

## Scope

Phase 3 extends the physical space model with satellite velocity, ground-referenced range rate, first-order Doppler shift, one-way propagation delay, and a free-space satellite link-budget state.

## Models

- Two-body Keplerian position and velocity in ECI.
- Earth-rotation transformation from ECI to ECEF.
- Ground observer velocity induced by Earth rotation.
- Range rate from the radial component of relative velocity.
- First-order Doppler shift: `f_d = -f_c * v_r / c`.
- One-way propagation delay: `t = R / c`.
- Free-space path loss using the Friis equation.

## Engineering boundary

This phase deliberately does not yet model atmospheric attenuation, rain fade, antenna patterns, polarization mismatch, multipath fading, scintillation, coding/modulation link adaptation, or detailed 3GPP NTN channel models. Those belong to later phases and will be added as separate, testable models.
