# Phase 6 — Ground Mobility and Handover Foundation

Phase 6 adds deterministic ground-user mobility and a baseline satellite handover controller on top of the validated physical and constellation layers.

## What this phase models

- WGS84 ground-user position evolution from local north/east/vertical velocity.
- Multiple mobile users can be evaluated independently.
- Satellite link candidates are computed from the user's current physical position.
- A deterministic handover baseline uses serving-link availability, hysteresis, and time-to-trigger.
- Handover events are explicit and testable: attach, retain, handover, and no coverage.

## What this phase does not claim

The mobility model is a controlled engineering approximation: constant velocity in the local tangent plane. It is not a city-scale road-network model, GNSS trace, or commercial 3GPP mobility simulator.

The handover policy is a baseline, not AI. Later predictive/autonomous policies will be compared against it.
