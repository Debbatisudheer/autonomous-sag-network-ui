# Phase 71 — Hardware Edge Deployment — LOCKED

Phase 71 is locked after Windows validation: Ruff passed, mypy passed on 238 source files, 531 tests passed, and the synthetic constrained-edge runtime passed. The local-host and verified OPS-SAT replay paths also passed during validation.

Evidence boundary: synthetic and local-host execution are retained as such. `--local-host` is not dedicated field-edge hardware evidence. OPS-SAT execution is historical public-data replay. No external network was used or mutated.

Windows portability correction: the over-budget test uses a near-zero wall-time budget rather than depending on Windows process-time timer resolution.
