# Phase 78 — Real-World Resilience Campaign

Phase 78 exercises the locked Phase 77 closed-loop autonomy system against bounded, deterministic fault injections.
It preserves the Phase 76/77 candidate and telemetry boundaries and adds campaign-level measurements for response and recovery.

The control sequence is:

`Observe -> Inject Fault -> Decide -> Act in software state -> Verify -> Recover -> Record`

The implementation uses candidate copies, not live network objects. Resource outage and domain outage faults change only
the copied `UnifiedCandidate` availability flag. Capacity-degradation faults change only the copied estimated-capacity field.
Telemetry degradation changes only the effective campaign telemetry-health gate. The underlying Phase 77/76 network state remains untouched.

The campaign records:

- fault-active cycles;
- impacted users;
- attach, retain, and handover actions;
- no-coverage events;
- telemetry-gate blocks;
- verification failures;
- demand-satisfaction ratio;
- first post-failure recovery time and latency;
- maximum unmet demand.

The default campaign contains seven scenarios spanning single-resource failure, whole-domain isolation, telemetry degradation,
capacity collapse, and cascading service isolation. Outcomes are reported as measured behavior. A recovered scenario means that
a post-failure cycle was observed in which all users were demand-satisfied with successful verification; it does not imply that
the system is physically resilient under arbitrary conditions.

Optional OPS-SAT replay is verified from the existing public-data provenance boundary, and optional SGP4 execution uses the
existing bundled point-in-time ISS/ZARYA TLE. Neither is represented as a physical end-to-end SAG failure measurement.
No external network infrastructure or physical RF/hardware actuation is invoked.
