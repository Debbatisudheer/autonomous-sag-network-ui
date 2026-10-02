# Phase 26 — Real Ground Geospatial Data

Phase 26 replaces ground-site coordinates that were previously supplied only by scenario configuration with explicit real-world geospatial ingestion boundaries.

## Architecture

`External geospatial source -> adapter -> validation -> provenance -> deterministic fingerprint -> GroundNetwork builder -> existing RF/link model`

## Sources

`NominatimClient` provides explicit, low-rate OSM geocoding/search. `load_ground_sites_geojson()` provides deterministic offline ingestion for point datasets. `USGSElevationClient` provides an explicit USGS 3DEP point-elevation path; it is not presented as global elevation coverage.

The existing `GroundCell` and ground-link calculations remain the authoritative radio model. Phase 26 only supplies better geospatial inputs and provenance; it does not invent measured RF parameters.

## Offline fixture boundary

The bundled India fixture contains city-reference coordinates for deterministic tests. It must not be interpreted as a measured cellular tower dataset. Real network sites should be ingested from an identified geospatial source and preserved with source identifiers/tags.

## Provenance and reproducibility

Every imported site retains source type, source URI, optional source feature ID, feature type, and tags. Dataset fingerprints are SHA-256 hashes of canonical site content sorted by site identifier.

## Ground elevation

Elevation enrichment is represented separately from the site's original coordinate. A provider result does not silently rewrite the source coordinate. This makes source/model boundaries auditable.
