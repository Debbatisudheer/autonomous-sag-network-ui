# Phase 8 — Air Network: UAV, HAPS, Mobility, and Energy

## Purpose

Phase 8 adds the airborne domain to the validated Ground + Space baseline.

## Scope

- UAV communication-platform model
- HAPS communication-platform model
- WGS84 aerial position and deterministic mobility
- User-to-air-platform link budgets using shared validated physics
- Explicit service-distance constraints
- Onboard energy accounting in Wh under a configured power model
- Energy reserve constraint for service availability
- Remaining-energy and time-to-reserve telemetry
- Multi-user air association with load and energy awareness

## Modeling boundary

This phase is intentionally an engineering baseline. It does not claim to model a specific aircraft, commercial UAV platform, HAPS vehicle, flight-control system, battery chemistry, propulsion system, 3GPP aerial channel model, antenna pattern, or operational airspace.

The aerial link currently uses WGS84 geometry plus the shared free-space link-budget model and explicit configured losses. Aerial energy is modeled from configured hotel and propulsion power, producing deterministic energy state rather than fabricated battery measurements.

UAV horizontal/vertical movement uses the same local tangent-plane mobility abstraction already validated for ground users. The baseline HAPS model is fixed in position; a future flight-dynamics model can replace it behind the same platform interface.

## Why this phase matters

The final autonomous system must choose among ground, aerial, and space connectivity. Phase 8 provides the aerial state needed to make those domains comparable later without changing the earlier validated satellite or ground modules.
