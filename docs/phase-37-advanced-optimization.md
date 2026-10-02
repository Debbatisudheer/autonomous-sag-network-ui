# Phase 37 — Advanced Optimization

Phase 37 adds a deterministic bounded multi-objective optimization layer on top of the validated Phase 19 optimizer and Phase 36 learned decision engine.

## Scope

- Preserve Phase 19 feasible-action generation and hard constraints.
- Build a deterministic Pareto frontier over feasible actions using objective score and expected gain.
- Search combinations with a bounded beam-search strategy rather than relying only on greedy ranking.
- Enforce one selected action per source.
- Enforce a configurable maximum number of selected actions targeting the same resource.
- Reward expected gain and resource diversity with explicit deterministic weights.
- Produce stable, reproducible selections without random optimization.
- Do not mutate network state during optimization.
- Preserve the existing `OptimizationPlan`, `ControlAction`, and control-execution contracts.

## Important boundary

Phase 37 is an optimization/search layer. It does not claim real-world network deployment, and the demo fixture is synthetic.

The existing Phase 19 optimizer remains the source of candidate actions and feasibility constraints. Phase 37 re-optimizes that candidate set; it does not bypass the established decision or control layers.
