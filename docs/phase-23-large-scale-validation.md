# Phase 23 — Large-Scale Validation

## Purpose

Phase 23 validates the autonomous Space–Air–Ground software testbed at increasing workload scale using deterministic benchmark scenarios. The phase validates composition and scalability of the existing telemetry, prediction, decision, optimization, recovery, and distributed-edge layers without replacing the underlying physical or networking models.

## Validation loop

`Scenario Generation -> Telemetry -> Prediction -> Decision -> Optimization -> Fault Injection -> Recovery -> Distributed Execution -> Metrics -> Benchmark`

## Deterministic benchmark design

The scenario generator uses explicit mathematical fixtures rather than random values. Each user receives the same three logical resource candidates (`gnd-a`, `uav-a`, `leo-a`) with deterministic parameter offsets by user index. Interference, traffic, and failure conditions are configured scenario inputs. These are benchmark workload parameters, not fabricated measurements presented as physical RF results.

## Scale matrix

The reference matrix covers 10, 50, 100, 250, and 500 users. Each scenario exercises three candidates per user, deterministic SINR telemetry histories, predictive threshold warnings, bounded decisions, optimization, deterministic fault injection, recovery, and distributed pipeline execution.

## Failure and resilience validation

A configurable fraction of users can receive a failed `uav-a` candidate. Recovery is expected to select an available alternative and verify the simulation-side reroute. The phase does not claim physical fault repair or standards-complete signaling.

## Distributed validation

The distributed fabric is exercised with Ground Edge, Air Edge, Regional, and Central controller nodes. The seven existing autonomous pipeline stages are replicated across a bounded number of representative sources. The validator checks placement completion, queue-safe execution, replicated state convergence, and exactly-once logical message delivery for the benchmark message.

## Performance metrics

Each scenario reports wall-clock runtime for engineering benchmarking plus deterministic logical metrics: user count, candidate count, telemetry records, predictive warnings, decisions, control actions, failures, recovered failures, distributed tasks, task completion ratio, recovery ratio, state convergence, message delivery, and a deterministic logical fingerprint. Runtime is intentionally excluded from the deterministic fingerprint because wall-clock performance varies by machine and process state.

## Modeling boundary

Phase 23 is a validation and benchmarking layer. It does not claim that the generated benchmark fixtures are measured RF/NTN observations. Physical realism remains provided by the underlying Phase 2–14 analytical models, while Phase 23 validates system composition, reproducibility, resilience, and scaling behavior over deterministic states.
