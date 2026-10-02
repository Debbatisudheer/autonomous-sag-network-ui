# Phase 5 — Multi-Satellite Constellation and Deterministic Selection

Phase 5 adds the first multi-satellite network layer on top of the validated physical link model.

## Added

- deterministic satellite definitions and constellation validation;
- active-member filtering;
- propagation of all active satellites at a common simulation time;
- ground visibility for every active satellite;
- pass prediction with configurable sampling and sub-second AOS/LOS boundary refinement;
- a deterministic safety-first satellite-selection baseline using measured link metrics.

## Important modeling boundary

The demo constellation is an **analytical engineering constellation**, not a claim about a real operator's deployed constellation. Its orbital elements are deterministic test inputs. No measured link-quality values are fabricated.

The orbital model remains the project's validated two-body Keplerian + Earth-rotation model. It is appropriate for a controlled software testbed and is not yet a substitute for high-fidelity SGP4/TLE propagation, Earth orientation products, atmospheric models, or operator ephemerides. Those will be explicit future adapters rather than hidden approximations.

## Why this phase exists

The project now has a measurable baseline for the eventual AI layer:

1. compute each satellite's physical state;
2. calculate visibility and link quality;
3. identify current and future visibility windows;
4. select a feasible satellite using a deterministic policy.

The future predictive/AI policy will be evaluated **against this baseline**, not against an undefined or hand-tuned outcome.
