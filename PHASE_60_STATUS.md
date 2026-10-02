# Phase 60 — Real-Time Data Validation

Status: Implemented; awaiting Windows final gate.

Evidence classes: SYNTHETIC FIXTURE by default; PUBLIC DATA when `--opssat-file` is supplied with the verified Phase 56 dataset.

Phase 60 adds an explicit validation boundary before normalized telemetry reaches the authoritative `TelemetryStateStore` through the Phase 59 ingestion pipeline.

Capabilities include:

- finite timestamp and telemetry-value validation
- invalid-quality rejection
- future-timestamp validation with configurable skew
- duplicate record-ID validation
- per-source/metric sequence monotonicity validation
- per-source/metric timestamp ordering validation
- deterministic validation rejection accounting
- deterministic SHA-256 validation fingerprints
- optional integration with `RealTimeTelemetryIngestion`
- no physical network mutation or external broker dependency
- no invented physical or instrument-specific limits

Default demo:

`python scripts/run_phase60_realtime_data_validation.py`

Public OPS-SAT replay validation:

`python scripts/run_phase60_realtime_data_validation.py --opssat-file data/raw/opssat-ad/segments.csv --limit 1000`

The public-data path validates historical public telemetry records after adapter normalization. It is not a claim of live spacecraft telemetry.
