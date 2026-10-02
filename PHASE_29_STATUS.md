# Phase 29 — Real Telemetry Adapters

Status: IMPLEMENTED ON TOP OF THE PHASE 28 CODEBASE

Implemented:
- Absolute UTC to deterministic simulation time mapping
- Explicit-schema streaming CSV adapter
- ESA OPS-SAT / OPSSAT-AD `segments.csv` adapter
- SatNOGS decoded telemetry JSON adapter with optional HTTP retrieval
- CCSDS 133.0-B-2 primary-header and contiguous-stream parsing
- Telemetry/telecommand identification, APID, sequence count, and packet-length validation
- Deterministic SHA-256 provenance fingerprints
- Preservation of source metadata
- Integration with the existing `TelemetryStateStore`
- Offline synthetic schema fixtures explicitly marked as non-measurements

Validation in this environment:
- `tests/test_telemetry_adapters.py`: 20 passed
- `compileall`: 0 errors
- Phase 29 demo: pass
- OPS-SAT schema-fixture demo: pass

Final Windows gate still required:
- `ruff check .`
- `mypy src`
- `pytest`
- `python scripts\run_phase29_real_telemetry_adapters.py`

Do not treat Phase 29 as locked until the Windows final gate is clean.
