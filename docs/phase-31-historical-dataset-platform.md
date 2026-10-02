# Phase 31 — Historical Dataset Platform

Phase 31 adds a reproducible historical telemetry layer on top of the Phase 30 real-time transport and the existing `TelemetryRecord` contract.

## Scope

- Partitioned historical telemetry storage using deterministic JSONL artifacts.
- Explicit dataset lifecycle: `building` → `sealed`.
- Immutable sealed datasets.
- Deterministic record ordering by simulation time, sequence, then record ID.
- Dataset manifests with record counts, time bounds, partition fingerprints, source fingerprints, and a dataset SHA-256 fingerprint.
- Historical queries by time window, source, network domain, metric, quality, and result limit.
- Duplicate record-ID protection.
- No external corpus is bundled; the Phase 31 fixture is synthetic and explicitly identified as such.

## Architecture

```text
Telemetry adapters / Phase 30 transport
              |
              v
       TelemetryRecord
              |
              v
   HistoricalDatasetStore
       |            |
       v            v
 partitioned      manifest
 JSONL files      + SHA-256
       |
       v
 HistoricalQuery -> HistoricalQueryResult
```

## Design rule

Phase 31 does not replace `TelemetryStateStore` or the real-time transport. It adds a historical persistence/query path using the same normalized telemetry contract.

## Validation

The required gate remains:

```text
ruff check .
mypy src
pytest
python scripts\\run_phase31_historical_dataset.py
```
