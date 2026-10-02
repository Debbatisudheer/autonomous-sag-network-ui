# Autonomous Predictive Space-Air-Ground Network

High-fidelity software engineering and research testbed for predictive autonomous orchestration across terrestrial, aerial, and non-terrestrial wireless networks.

## Phase status

- Phase 1: Engineering foundation — complete
- Phase 2: Earth + LEO geometry — complete
- Phase 3: Satellite dynamics — complete
- Phase 4: NTN link budget — complete
- Phase 5: LEO constellation + pass prediction — complete
- Phase 6: User mobility + handover — complete
- Phase 7: Terrestrial ground network + multi-user state — complete
- Phase 8: UAV/HAPS + aerial mobility + energy — complete
- Phase 9: Unified Ground + Air + Space network state — complete
- Phase 10: Cross-domain Ground ↔ Air ↔ Space handover baseline — complete
- Phase 11: End-to-end topology + deterministic routing baseline — complete
- Phase 12: Traffic demand + QoS admission and shared path capacity — complete
- Phase 13: Resource and spectrum management — complete
- Phase 14: Interference and channel effects — complete
- Phase 15: Digital twin state synchronization and deterministic history — complete
- Phase 16: Telemetry and real-time state — complete
- Phase 17: Predictive intelligence baseline — complete
- Phase 18: Explainable AI decision engine baseline — complete
- Phase 19: Optimization and autonomous control baseline — complete
- Phase 20: Failure recovery and self-healing baseline — complete
- Phase 21: Security — deferred by project decision
- Phase 22: Edge + distributed architecture — complete
- Phase 23: Large-scale validation — complete
- Phase 24: Final autonomous SAG platform — complete
- Phase 25: Real satellite ephemeris — complete
- Phase 26: Real ground geospatial data — complete
- Phase 27: Real UAV/HAPS mobility data — complete
- Phase 28: Higher-fidelity wireless / NTN channel — complete
- Phase 29: Real telemetry adapters — complete
- Phase 30: Real-time data transport — complete
- Phase 31: Historical dataset platform — complete
- Phase 32: ML predictive baseline — implementation complete; validation pending

## Phase 32 — ML Predictive Baseline

Phase 32 adds the first explicitly supervised machine-learning baseline above the Phase 31 historical dataset platform. It trains deterministic per-source/metric ridge regression models from lagged telemetry, evaluates them using a chronological holdout, fingerprints the learned coefficients, and emits recursive multi-step forecasts. The implementation is a research baseline rather than a claim of production-grade ML accuracy. The bundled fixture is synthetic.

## Engineering principle

Every new phase is additive. Existing validated physics and tests remain intact.

The platform uses analytical and deterministic models where appropriate and labels modeling boundaries explicitly. It does not claim that simulated nodes, satellites, UAVs, HAPS platforms, or 6G infrastructure are physical deployments.

Phase 10 boundary:

The cross-domain controller is a deterministic mobility-management baseline. It uses measured candidate link state from the existing Ground, Air, and Space models, with hysteresis and time-to-trigger. It is not a full 3GPP inter-RAT signaling implementation.

Phase 9 boundary:

The unified layer composes the validated Ground, Air, and Space models into one common candidate/state schema. It does not replace their physical calculations. The baseline selector is deterministic and non-AI; future predictive/AI policies will be evaluated against it.

Core loop planned for later phases:

`Sense -> Predict -> Simulate -> Decide -> Coordinate -> Act -> Measure -> Learn`

Phase 18 boundary:

The AI decision layer converts predictive warnings into bounded, explainable action proposals. The current policy is deterministic and pluggable; it is not presented as a trained machine-learning model. Execution and autonomous control are deferred to Phase 19.


## Phase 11 — Topology and Routing

Phase 11 adds end-to-end topology and deterministic routing across access resources, gateways, core, and service nodes. The router consumes measured UnifiedCandidate state from the existing Ground/Air/Space models and derives path latency, bottleneck capacity, and composed loss.


## Phase 12 — Traffic and QoS

Phase 12 adds explicit traffic flows and service requirements above the existing routing layer. Traffic is evaluated using configured demand, minimum throughput, maximum latency, maximum loss, and priority. The baseline performs deterministic admission with shared path-capacity accounting. It reuses Phase 11 route metrics rather than inventing new radio measurements.

The Phase 12 service classes are configurable scenario parameters and are not presented as a standards-complete 3GPP QoS implementation. Packet-level queues, application traffic models, scheduler-specific behavior, and advanced congestion control are intentionally deferred to later phases.


## Phase 14 — Interference and Channel Effects

Phase 14 adds deterministic co-channel and partially overlapping-channel interference, linear-domain
interference aggregation, explicit channel loss, and recomputed SINR/capacity/link margin. The
resulting degraded `UnifiedCandidate` state can be consumed directly by the Phase 13 spectrum
scheduler. The phase is intentionally not presented as a complete 3GPP PHY/MAC model.


## Phase 15 — Digital Twin

Phase 15 establishes a versioned digital representation of validated SAG state. It synchronizes
unified network state with optional topology, spectrum, and interference state; computes deterministic
SHA-256 snapshot hashes; retains bounded history; and detects structural state deltas. It is a state
mirror rather than a replacement for the underlying physics or networking models.


## Phase 19 — Optimization and Autonomous Control

Phase 19 adds a deterministic constrained optimizer and simulation-side control executor above the Phase 18 decision layer. It scores decision proposals using explicit utility, priority, capacity, margin, latency, resource-balance, and switching terms, applies configurable capacity/utilization/availability constraints, and selects a bounded action set. The control executor mutates a dedicated versioned control state, then verifies each action against the current network and resource state. The phase is a software control-plane testbed; it does not claim physical network command execution or standards-complete RAN/NTN signaling.


## Phase 20 — Failure Recovery and Self-Healing

Phase 20 consumes synchronized telemetry and network state to detect hard failures, diagnose deterministic root causes, construct bounded recovery plans, and apply recovery actions through the existing Phase 19 simulation-side control plane. It tracks active/recovered faults and recovery attempts, verifies actuation results, and keeps telemetry-refresh actions in a recovering state until a fresh observation can confirm restoration. Stable fault signatures provide correlation across simulation timestamps. The phase remains a software self-healing testbed and does not claim physical repair or standards-complete control-plane signaling.

## Phase 21 — Security

Security is intentionally deferred. The architecture preserves explicit extension boundaries for future authentication, authorization, integrity, secure transport, threat detection, and audit controls without coupling those concerns into the current simulation core.

## Phase 22 — Edge and Distributed Architecture

Phase 22 adds the logical distributed compute fabric: edge/regional/central nodes, capability-aware workload placement, bounded distributed task execution, deterministic inter-node messaging, versioned state replication and convergence, and a pipeline adapter spanning telemetry, prediction, decision, optimization, recovery, and Digital Twin synchronization.


## Phase 23 — Large-Scale Validation

Phase 23 validates the integrated autonomous pipeline at deterministic workload scales of 10, 50, 100, 250, and 500 users. It exercises telemetry history generation, predictive warnings, bounded decision selection, optimization, deterministic fault injection and recovery, and distributed edge/regional/central execution. Runtime is measured as an engineering benchmark, while logical scenario fingerprints exclude wall-clock timing for reproducibility.


## Phase 24 — Final Autonomous SAG Platform

Phase 24 integrates the validated autonomous control-plane subsystems into one deterministic platform orchestrator. One cycle consumes validated network state and telemetry, synchronizes the Digital Twin, runs predictive intelligence, selects explainable decisions, optimizes and verifies control actions, executes failure recovery when a fault-injected state is supplied, distributes the autonomous pipeline across edge/regional/central compute, and produces a closed-loop feedback report with a deterministic fingerprint.

The platform remains a high-fidelity software engineering/research testbed. Security Phase 21 is intentionally deferred.

## Phase 25 — Real Satellite Ephemeris Integration

Phase 25 adds the first real-world data path. The project now accepts validated TLE and OMM data, uses the `sgp4` propagator for absolute-time satellite states, converts TEME states to Earth-fixed coordinates, provides a refreshable CelesTrak client, and exposes those real states through the existing satellite candidate/link machinery. The analytical two-body model remains available as a deterministic reference baseline.

The bundled `data/ephemeris/iss-zarya.tle` is a point-in-time real element set for ISS (ZARYA), NORAD 25544. It is a test fixture, not a permanently current operational ephemeris.

## Phase 26 — Real Ground Geospatial Data

Phase 26 adds explicit real-world geospatial input adapters for ground sites. It supports GeoJSON point ingestion with provenance and deterministic fingerprints, low-rate OpenStreetMap Nominatim search, and an explicit USGS 3DEP elevation provider boundary. These adapters feed the existing GroundNetwork/GroundCell contract without changing the validated RF calculations. The bundled India fixture is a city-reference dataset for deterministic offline tests, not a telecom-tower inventory.


## Phase 27 — Real UAV/HAPS Mobility Data

Phase 27 adds external aerial-trajectory ingestion for real UAV data and a common contract for real HAPS trajectories. The implementation supports JSONL, CSV, and timestamped GeoJSON observations, UTC normalization, WGS84-derived local kinematics, bounded interpolation, provenance/fingerprinting, and projection into the existing AirNetwork/AirPlatform contracts. The bundled ORION sample is a small third-party excerpt retained with a separate license notice; the full upstream dataset is not redistributed.


## Phase 28 — Higher-Fidelity Wireless / NTN Channel

Phase 28 adds a dedicated deterministic channel-realization layer above the validated real-ephemeris and aerial/ground foundations. It models elevation-dependent NTN LOS/NLOS conditions, 3GPP TR 38.811 shadowing and NLOS clutter reference values, correlated shadow fading, Doppler-derived coherence, correlated Rician/Rayleigh fast fading, and geometry-scaled weather attenuation inputs. The layer integrates with the existing satellite link budget without changing the baseline SGP4 or candidate contracts.

The phase is a higher-fidelity engineering/research channel model, not a complete 3GPP NR PHY or full TR 38.811 link-level implementation. Full TDL/CDL channel synthesis, antenna-array spatial filtering, exact ITU-R site-climate prediction, and hardware/measurement-calibrated channel models remain future extensions.
