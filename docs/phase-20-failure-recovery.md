# Phase 20 — Failure Recovery and Self-Healing

Phase 20 adds a deterministic failure-management layer above the Phase 16–19 telemetry, prediction,
decision, optimization, and simulation-side control planes.

## Core loop

`Telemetry + Network State -> Failure Detection -> Diagnosis -> Recovery Planning -> Autonomous Recovery -> Verification -> State Reconciliation`

## Detection scope

The detector recognizes:

- telemetry staleness
- unavailable selected links
- observed resource/node failure when all observed links to a resource are unavailable
- resource utilization exhaustion
- remaining-capacity exhaustion
- failed handover preparation
- failed rerouting control actions

Hard failures are kept distinct from ordinary predictive degradation. A predicted warning remains a
Phase 17/18 concern; Phase 20 acts on observed or verified failure evidence.

## Diagnosis

Each event maps to an explicit root-cause category and recommended recovery-action classes. Diagnosis is
deterministic and explainable; it does not claim a fault-classification ML model.

## Recovery actions

The recovery vocabulary covers rerouting, handover preparation, spectrum reservation, reservation release,
load reduction, resource pre-positioning, and telemetry refresh requests.

Actions are bounded by configured alternative link margin/capacity thresholds and a maximum number of
actions per cycle. A telemetry refresh request is intentionally reported as `recovering`, not falsely
marked as verified until a fresh observation arrives.

## Control integration

Recovery actions that correspond to existing Phase 19 control operations are translated into the existing
`ControlState`/`AutonomousControlExecutor` contracts. This preserves one simulation-side actuation boundary
rather than creating a second incompatible control system.

## Fault correlation and retry behavior

Failure event IDs are stable for the same fault signature across observation timestamps. The self-healing
state tracks active events, recovered events, refresh requests, and per-event recovery-cycle attempts.
The maximum recovery-attempt boundary prevents unbounded repeated actuation.

## Modeling boundary

Phase 20 is a software self-healing testbed. It does not claim physical network repair, hardware reboot,
3GPP-complete control-plane signaling, satellite fleet command execution, or an ML root-cause model.
Adapters for real emulators, SDRs, operator APIs, or hardware can implement the same contracts later.
