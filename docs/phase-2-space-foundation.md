# Phase 2 — Space Physical Foundation

## Scope

Phase 2 introduces the first physically grounded space-domain models:

- WGS84 geodetic-to-ECEF conversion
- two-body Keplerian orbit propagation
- Earth rotation from ECI to ECEF
- ground-to-satellite topocentric geometry
- elevation-angle visibility threshold
- slant-range calculation

## Current assumptions

This phase deliberately uses a transparent two-body orbital model. It is not yet a replacement for a precision orbit-determination library or a TLE/SGP4 pipeline. Those can be added later as higher-fidelity inputs and cross-validation sources.

The system keeps reference frames explicit. ECI and ECEF are stored separately to prevent accidental mixing of inertial and Earth-fixed coordinates.

## Validation

The tests verify WGS84 reference geometry, orbital-radius preservation, Earth rotation, state consistency, and visibility behavior.

## Next physical layers

1. satellite velocity from the propagated state
2. range rate and Doppler shift
3. satellite link budget using slant range
4. elevation-dependent propagation/antenna constraints
5. multi-satellite pass generation
6. optional TLE/SGP4 validation path
