# SAG Live UI Showcase v0.8

## Scope
Dedicated Mission Control workspaces layered over the frozen SAG Network v2.0.0 codebase. The `src/` and `data/` trees are not modified by this showcase increment.

## New functionality
- Shared workspace navigation: Overview, Network Map, Telemetry, Prediction / Decision, Autonomy, Resilience.
- All workspaces consume the same runtime state produced by the existing showcase server and real SAG engines.
- Dedicated Telemetry Operations view with actual selected-resource link-margin history and live control-health values.
- Dedicated Prediction & Decision Operations view with actual current/selected resource, link margin, capacity, telemetry gate, verification and Phase 76 candidate set.
- Dedicated Autonomy Operations view with the actual Phase 77 execution pipeline and live engine events.
- Existing Network Map and Resilience views remain available without changing backend behavior.
- Navigation switches views without fabricating independent state.

## Validation
- `node --check showcase/app.js` PASS
- `python -m py_compile showcase/server.py` PASS
- `/api/topology?mode=synthetic&time=0`: 8 nodes, 31 orbit points, center 17.390N/78.4867E
- `/api/candidates?mode=synthetic&time=2400&user=sag-user-03`: 5 actual candidates, selected `air-haps-01`
- `/api/resilience?mode=synthetic`: 7 scenarios, 231 cycles, 7/7 recovered, 30 handovers, 225 verification passes, 6 verification failures, 93.506% demand satisfaction, 97.403% verification success, 25.714s mean recovery, 180s max recovery

## Evidence boundary
`network_mutation=false`, `hardware_measurement=false`, deterministic software execution. Public/synthetic/replay evidence remains explicitly labeled.
