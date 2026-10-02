# Phase 22 — Edge and Distributed Architecture

Phase 22 introduces a deterministic distributed compute fabric for the autonomous SAG testbed.

## Scope

The phase adds logical edge, regional, and central compute nodes; workload placement; bounded task execution; versioned replicated state; deterministic message envelopes; an in-memory broker; and a pipeline-task adapter for the existing telemetry, prediction, decision, optimization, recovery, and digital-twin stages.

## Architecture

`SAG observations → edge ingestion → state aggregation → prediction → decision → optimization → recovery → Digital Twin synchronization`

The stages are represented as distributed tasks and can be placed on different compute tiers according to capabilities, health, load, and latency constraints.

## Placement model

Placement is deterministic and considers:

- required execution capabilities,
- CPU and memory headroom,
- queue capacity,
- node health/active state,
- processing plus network latency,
- preferred network domain,
- bounded per-task latency.

This is a scheduling baseline, not a claim of standards-complete MEC, 3GPP edge orchestration, or physical multi-site deployment.

## Distributed state

State replicas are versioned per node. Older versions and timestamp-regressive updates are rejected. Identical replicas are recognized as converged through a deterministic SHA-256 state hash.

## Messaging

Messages use deterministic payload hashes and message IDs with bounded TTL. The broker is an in-memory simulation component intended to preserve interface boundaries before a production transport such as Kafka, NATS, QUIC, or another deployment-specific bus is selected.

## Security boundary

The full Security phase is intentionally deferred. Phase 22 therefore does not add authentication, authorization, cryptographic key management, or secure transport. The distributed interfaces remain explicit so those concerns can be layered later without redesigning the simulation core.

## Validation

Phase 22 adds unit coverage for placement, node health/capacity constraints, message determinism and expiry, state replication/convergence, pipeline stage construction, task execution, and rejected workloads.
