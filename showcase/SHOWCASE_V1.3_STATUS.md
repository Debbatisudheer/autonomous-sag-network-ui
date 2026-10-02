# SAG Network Live UI v1.3

## Purpose
Presentation-clarity refinement on top of the existing SAG v2.0.0 runtime. The frozen SAG `src/` and `data/` trees are not modified.

## Changes
- Network State now labels the availability metric as `Available / user` to make its scope explicit.
- The Current Decision card uses `Previous resource` for the pre-action resource; selected resource remains the post-decision selection.
- Prediction & Decision view uses the same `Previous resource` wording.
- Live execution header now reports the actual cycle index and simulation timestamp while the Phase 77 SSE stream is running.
- Available candidates for the current user are counted from the actual Phase 76 candidate response and shown in the Network State card.
- Mode switches clear the scoped availability value until the next real candidate response arrives.

## Validation
- `python -m py_compile showcase/server.py` PASS
- `node --check showcase/app.js` PASS
- `/api/topology` validated: 8 nodes, 31 orbit points
- `/api/candidates` validated: 5 candidates for a user, 1 available in the tested deterministic snapshot
- `/api/resilience` validated: 231 cycles, 7/7 recovered, 30 handovers, 225 verification passes, 6 verification failures, 93.51% demand satisfaction, 97.40% verification success, 25.71 s mean recovery, 180 s maximum recovery

## Evidence boundary
- network_mutation=false
- hardware_measurement=false
- deterministic=true
