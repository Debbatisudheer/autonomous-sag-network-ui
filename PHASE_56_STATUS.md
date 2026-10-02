# Phase 56 — Real-World Data Acquisition

Status: Implemented; Windows final gate pending.

Scope:
- Public real-data acquisition boundary for OPSSAT-AD `segments.csv`.
- Explicit dataset version, source URI, provenance and evidence classification.
- MD5 verification against the publisher's published checksum.
- SHA-256 fingerprint and byte-count capture.
- Deterministic provenance manifest.
- No network mutation; acquisition is read-only.

Evidence:
- Dataset: OPSSAT-AD anomaly-detection dataset for satellite telemetry.
- Version: v2, Zenodo record 15108715.
- Evidence class: PUBLIC DATA.
- The dataset is not bundled into the source release; it must be acquired with `--download`.

Validation command:
`python scripts\\run_phase56_real_data_acquisition.py --download`
