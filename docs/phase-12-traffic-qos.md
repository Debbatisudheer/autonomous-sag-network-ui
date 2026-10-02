# Phase 12 — Traffic and QoS

Phase 12 adds application traffic demand and explicit QoS requirements above the validated physical, unified, and routing layers.

## What is modeled

- traffic flows with explicit bitrate demand;
- configurable service classes: conversational, interactive, streaming, and best-effort;
- minimum throughput, maximum latency, maximum loss, and priority requirements;
- deterministic priority-based admission;
- shared end-to-end link-capacity accounting;
- QoS rejection when throughput, latency, or loss requirements cannot be met;
- reuse of Phase 11 route latency, bottleneck capacity, and end-to-end loss without recomputing radio measurements.

## Modeling boundary

The service-class values in the demonstration are **scenario parameters**, not claims about a specific 3GPP service profile. The traffic layer also does not yet model packet-level queues, TCP congestion control, scheduler-specific PHY/MAC behavior, application codecs, or stochastic traffic generators. Those concerns are intentionally separated so later phases can add them behind explicit interfaces.

The current admission model is deterministic: higher-priority flows are considered first, and a flow is admitted only when its configured QoS requirements fit within residual path capacity and the measured route latency/loss.
