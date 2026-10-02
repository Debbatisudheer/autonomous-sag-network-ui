# Phase 25 — Real Satellite Ephemeris Integration

## Purpose

Phase 25 replaces the Phase 1–24 analytical satellite-state input with a real-data integration path while retaining the existing two-body propagator as a deterministic reference model.

## Real-world data path

```text
CelesTrak GP data / TLE / OMM
        ↓
Validated ephemeris record
        ↓
SGP4 propagator
        ↓
TEME position + velocity
        ↓
TEME → ECEF frame adapter
        ↓
Real satellite state
        ↓
Existing NTN link / candidate calculations
```

CelesTrak documents GP/TLE and modern OMM formats, including JSON, CSV, KVN, and XML. The site also provides a direct GP query for individual catalog numbers. The project uses the public GP endpoint for its refreshable data source. The bundled ISS fixture is a point-in-time snapshot and must not be treated as permanently current.

The Phase 25 SGP4 integration uses the `sgp4` Python package. That project wraps the official C++ implementation associated with Revisiting Spacetrack Report #3 and supports loading TLE and OMM element sets.

## Implemented components

- `sag_network.ephemeris.models`
  - validated TLE records
  - OMM records
  - real satellite state
  - simulation-clock configuration
- `sag_network.ephemeris.tle`
  - TLE checksum validation
  - TLE parsing
  - TLE epoch conversion
  - analytical-reference orbital element conversion
- `sag_network.ephemeris.omm`
  - OMM JSON parsing
  - OMM CSV parsing
- `sag_network.ephemeris.sgp4`
  - runtime SGP4 backend
  - TLE initialization
  - OMM initialization
  - absolute UTC propagation
- `sag_network.ephemeris.frames`
  - Julian date conversion
  - GMST
  - TEME → ECEF position
  - TEME → ECEF velocity
- `sag_network.ephemeris.celestrak`
  - CelesTrak GP URL builder
  - current TLE retrieval
  - current OMM JSON retrieval
- `sag_network.ephemeris.reference`
  - relative simulation time → absolute UTC adapter
- `sag_network.space.real_connectivity`
  - reuse of the existing satellite link/candidate machinery with real SGP4 states

## Accuracy boundary

SGP4 produces a TEME state. Phase 25 converts that state to an Earth-fixed vector using GMST. Polar motion and UT1-UTC corrections are intentionally not applied yet; the frame adapter is isolated so an Earth-orientation-data implementation can replace it later without changing the ephemeris-provider contract.

The TLE-to-`OrbitalElements` conversion is a reference approximation only. It is used to compare the real SGP4 trajectory with the existing analytical model; it is not presented as a conversion to an equivalent osculating state.

## Fresh-data operation

The `CelesTrakClient` provides a refreshable data path. CelesTrak's current documentation explains that GP data can be requested by catalog number and returned as TLE or modern OMM formats. Because element sets age continuously, experiments should record the exact source, retrieval time, and element epoch with each run.

## Validation strategy

The Phase 25 tests verify:

- TLE checksum integrity
- field parsing
- epoch conversion
- OMM JSON/CSV parsing
- Julian-date and GMST calculations
- TEME/ECEF transformation behavior
- SGP4 adapter behavior through a test backend
- propagation error handling
- simulation-time mapping
- compatibility with the existing satellite candidate interface

The local developer environment must install `sgp4` to execute real SGP4 propagation. The bundled fixture is a real ISS element set retrieved from CelesTrak during Phase 25 development.
