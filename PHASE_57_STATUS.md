# Phase 57 — Dataset Provenance & Quality

Status: LOCKED

Evidence class: PUBLIC DATA.

The Phase 57 quality profiler was executed against the real OPSSAT-AD `segments.csv` acquired in Phase 56.

Windows final gate:
- Ruff: PASS
- mypy: PASS — 196 source files
- pytest: PASS — 472 tests
- Phase 56 acquisition validation: PASS
- Phase 57 real-dataset quality run: PASS

Real dataset evidence:
- Rows: 303,493
- Columns: 8
- Duplicate rows: 0
- Empty rows: 0
- Numeric columns: 5
- Timestamp column: `timestamp`
- Label columns: `label`, `anomaly`
- Split column: `train`
- Source SHA-256: `d5201e9e751eb2a53a0ff7c11567dc4239f594ea4b479b2aa66fe67ddcbcb9ba`
- Source MD5: `72f109630abb933a386106897a631188`
- Provenance verified: true
- Quality fingerprint: `e155947812ed4e33ab928816067e101f96a7cafe0f3efe6df7ef40f86d1080bd`
- Network mutation: false

The profiler checks CSV schema, row/column counts, null counts, duplicate rows, empty rows, numeric candidates, timestamp candidates, label candidates, split candidates, distinct-value counts, invalid numeric/timestamp values, source SHA-256, provenance-manifest linkage, and a deterministic quality fingerprint.

The actual real dataset remains external to this software release; the release contains the acquisition/provenance tooling and tests, not a bundled copy of the 18.9 MB public dataset.

Next phase: Phase 58 — Multi-Source Telemetry Fusion.
