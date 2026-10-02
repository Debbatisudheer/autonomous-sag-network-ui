# Phase 13 — Resource & Spectrum Management

## Scope

Phase 13 adds a deterministic access-spectrum scheduler on top of the existing Ground, Air,
Space, unified, routing, and Traffic/QoS models.

## Model

The scheduler treats each configured access resource as a shared spectrum pool divided into
configurable resource blocks. The physical candidate state is not regenerated. Instead, the
scheduler reuses the candidate's existing Shannon capacity as the full-bandwidth upper bound
and applies an explicit scheduler-efficiency factor.

For a resource with N resource blocks:

`scheduled_capacity = Shannon_capacity × scheduler_efficiency`

`capacity_per_block = scheduled_capacity / N`

A traffic request requiring R bps needs:

`required_blocks = ceil(R / capacity_per_block)`

Requests are processed by descending priority and flow ID for deterministic behavior. A
resource is feasible only if the candidate is available and enough resource blocks remain.

## Realism boundary

This phase is a scheduler abstraction, not a claim of a complete 3GPP NR MAC scheduler.
Resource-block width is configurable and intentionally generic. Exact 5G NR numerology,
link-adaptive MCS, HARQ timing, power control, inter-cell interference, and detailed PHY/MAC
behavior remain future work.

## Why this phase exists

Earlier phases established whether a link exists and what its physical capacity can support.
This phase establishes how that shared capacity is divided among competing traffic flows.
That state will later feed the predictive/autonomous decision layer.
