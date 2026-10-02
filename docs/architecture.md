# Architecture — Day 1 Foundation

## Principle

The platform is built as a modular, deterministic engineering testbed. Physical/network models are separated from orchestration and AI so every decision can be traced to measurable inputs.

## Initial layers

```text
Configuration
    |
    v
Domain Models
    |
    +--> Physics / Link Budget
    |
    +--> Simulation Engine
    |
    +--> Telemetry
    |
    v
Future: State Estimation -> Prediction -> Digital Twin -> Decision -> Orchestrator
```

## Design constraints

- Units are explicit in field names where ambiguity is possible.
- Simulation time is deterministic and independent of wall-clock time.
- Randomness, when later required, must use an explicit seeded generator.
- Physics calculations are pure functions where practical.
- Domain objects are validated at boundaries.
- Telemetry is structured and machine-readable.
- AI is not introduced until the baseline system and evaluation metrics exist.

## Future service boundaries

1. Scenario Service
2. Ground Network Model
3. Aerial Network Model
4. Satellite/NTN Model
5. RF/Channel Service
6. State & Telemetry Service
7. Digital Twin Service
8. Prediction Service
9. Decision/Optimization Service
10. Network Orchestrator
11. Evaluation Service
12. API/UI Gateway

## Phase 4 — Configurable NTN Link State

Phase 4 separates free-space path loss from explicit propagation and implementation losses and adds receiver noise, optional interference, SINR, link margin, and a Shannon capacity upper bound. Scenario losses are explicit inputs rather than fabricated runtime values.


## Phase 5 boundary

The constellation layer is intentionally separated from link physics and selection policy. Satellite propagation and visibility remain deterministic physical calculations; the selection module is a deterministic baseline only. Predictive AI is a later policy implementation that must be benchmarked against this baseline.


## Phase 6 boundary

Ground-user mobility is modeled as deterministic constant local tangent-plane velocity over WGS84. Mobility-aware satellite candidates reuse the existing physical propagation/link pipeline. Handover is an explicit baseline policy with hysteresis and time-to-trigger; it is intentionally separate from future predictive AI.


## Phase 7 boundary

The terrestrial baseline introduces ground cells as a second network domain. Ground-user links reuse the validated WGS84 geometry and transparent link-budget primitives. Multi-user association is deterministic and load-aware, and the per-user allocation is an analytical equal-share scheduling ceiling rather than measured application throughput.

The ground model deliberately does not yet claim a full 3GPP channel, beamforming, scheduler, or operator-network implementation. These capabilities can be added behind stable interfaces later. The next heterogeneous-network phases can consume both terrestrial and NTN candidate state without changing the underlying physical models.


## Phase 9 boundary

The unified network layer composes Ground, Air, and Space resources without duplicating or modifying their physical models. A common candidate schema exposes comparable state across domains. The baseline cross-domain association policy is deterministic and load-aware; it is explicitly a baseline for later predictive and AI policies.

## Phase 10 boundary

The cross-domain controller is a deterministic mobility-management baseline over the common Phase 9 candidate schema. It applies hysteresis and time-to-trigger across Ground, Air, and Space resources and immediately replaces an unavailable serving resource. It does not emulate or claim full 3GPP inter-RAT signaling, bearer transfer, authentication, session continuity, or commercial core-network procedures. Those are future integration boundaries.


## Phase 11 boundary

The topology/routing layer adds an end-to-end directed graph from user access resources through domain gateways and core to a service endpoint. User access edges are derived directly from `UnifiedCandidate` measurements. Configured backhaul links carry explicit capacity, latency, loss rate, and active state. Route selection is a deterministic lowest-latency baseline subject to availability, with bottleneck-capacity and end-to-end loss reported for the selected path. It does not yet claim full OSPF/BGP behavior, 5G Core procedures, inter-satellite links, or application-level transport behavior.
