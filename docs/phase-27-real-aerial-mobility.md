# Phase 27 — Real UAV/HAPS Mobility Data

Phase 27 replaces constant-velocity aerial input with an external-trajectory ingestion path while preserving the existing `AirNetwork`, `AirPlatform`, and RF/link contracts.

## Data flow

External trajectory file → validation → UTC normalization → WGS84 trajectory → kinematics/interpolation → `AirNetwork` projection → existing RF/link model.

## Design

`trajectory.models` contains the provenance-aware trajectory contract and radio projection profile.

`trajectory.loader` supports JSONL, CSV, and timestamped GeoJSON point observations. The JSONL path directly matches the ORION schema used by real drone-flight data: millisecond acquisition timestamp, latitude, longitude, and altitude.

`trajectory.kinematics` derives local north/east/up velocity from WGS84 ECEF displacement between observations. Interpolation is explicitly bounded by `maximum_interpolation_gap_s`; the implementation does not invent acceleration or aerodynamic behavior that is absent from the source data.

`trajectory.air` projects one external trajectory state into the existing `AirPlatform`/`AirNetwork` contract at a specified UTC time. This preserves compatibility with the existing Air RF model and downstream SAG stages.

## Realism boundary

This phase introduces a real external UAV trajectory path. It does not claim that a real UAV is transmitting a wireless signal or that the trajectory source contains radio measurements. RF properties still come from the existing configured radio/link model until later measurement/SDR phases.

HAPS support is contract-ready, but no real HAPS dataset is bundled in this phase.
