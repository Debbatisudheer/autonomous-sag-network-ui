# Phase 18 — AI Decision Engine

## Purpose

Phase 18 turns the predictive warning stream from Phase 17 into a bounded, explainable decision layer. It does not execute network control yet. Instead, it produces machine-readable action proposals, checks their current feasibility against the unified network state, ranks them deterministically, and emits explainable selected decisions.

## Core flow

`Predictive warnings -> Policy proposals -> Feasibility checks -> Utility ranking -> Bounded selection -> Explanation`

## Decision contracts

The phase introduces:

- `DecisionActionType`
- `DecisionStatus`
- `DecisionPriority`
- `DecisionConfig`
- `DecisionEvidence`
- `DecisionAction`
- `SelectedDecision`
- `DecisionReport`

The action vocabulary covers:

- prepare handover
- reserve spectrum
- reroute flow
- reduce load
- preposition resource
- no action

These are proposals, not actuator commands. Phase 19 is responsible for optimization and autonomous control.

## Policy architecture

`DecisionPolicy` is a protocol so the policy layer can later be replaced with learned models, reinforcement-learning policies, or an optimization-backed selector without changing the external decision contracts.

The Phase 18 implementation uses `ExplainablePredictivePolicy` as a deterministic baseline. This is deliberately not presented as a trained ML model. It uses predictive severity/confidence/lead time plus current candidate and spectrum state to construct feasible actions.

## Feasibility

Examples:

- predicted radio degradation requires an available alternative candidate with adequate link margin and positive estimated capacity
- predicted capacity degradation can request spectrum reservation when the current resource has confirmed remaining capacity and is below the configured utilization ceiling
- latency/utilization warnings can propose reroute or load-reduction actions when an alternative candidate exists
- energy/interference stress can propose pre-positioning when an alternative candidate exists

A warning with no current matching network state is represented as an infeasible action with an explicit constraint rather than silently being discarded.

## Ranking

Candidate utility is deterministic and combines policy utility with priority weight. Critical actions receive more weight than lower-priority actions. Selection is bounded by `maximum_actions` and limited to one selected action per warning source in one decision cycle.

Decision identifiers are stable SHA-256-derived identifiers over the timestamp and canonical action payload.

## Synchronization boundary

Predictive, unified-network, and optional spectrum snapshots must share the same simulation timestamp. This prevents the decision engine from selecting an action using temporally inconsistent state.

## Engineering boundary

Phase 18 is a decision proposal baseline. It does not:

- claim a trained neural network or reinforcement-learning model
- execute handovers, routing, or spectrum reservations
- implement a complete 3GPP control-plane protocol
- replace the Digital Twin
- replace the deterministic predictive baseline

Phase 19 will introduce optimization and autonomous control over these decision outputs.
