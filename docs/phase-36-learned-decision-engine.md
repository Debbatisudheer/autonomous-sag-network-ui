# Phase 36 — Learned Decision Engine

## Purpose

Phase 36 adds a deterministic learned-value layer above the validated Phase 18 decision-policy contract. It learns an action-value estimate from explicit historical decision/outcome examples and uses that estimate to re-rank actions already produced and feasibility-checked by the explainable predictive policy.

## Core flow

`Predictive warnings -> deterministic policy proposals -> feasibility -> learned value -> bounded decision selection`

## Learned model

The implementation uses a small regularized linear value model trained with deterministic ridge regression. Features include:

- baseline policy utility
- action feasibility
- action priority
- evidence confidence
- lead-time urgency
- alternative-resource availability
- constraint count
- action-type indicators

The model is deterministic and produces a SHA-256 fingerprint over its configuration, feature schema, learned coefficients and training-example count.

## Training boundary

Training requires explicit `DecisionLearningExample` records containing an action and an observed reward in `[0, 1]`. The project does not fabricate operational outcomes. Phase 36's offline runtime fixture is explicitly synthetic and is only used to validate the learning pipeline.

## Integration boundary

`LearnedDecisionPolicy` delegates action generation and feasibility to the existing `ExplainablePredictivePolicy`, then blends the learned value with the bounded baseline utility. This preserves the Phase 18 action vocabulary and feasibility checks.

The learned layer does not:

- execute network control
- mutate Digital Twin or network state
- invent labels from model predictions
- claim real-world operational training data
- replace the deterministic predictive or feasibility layers

## Validation

The phase requires:

- deterministic model training
- deterministic model fingerprint
- learned-policy integration tests
- Ruff and mypy clean
- full test suite
- deterministic Phase 36 runtime demo
