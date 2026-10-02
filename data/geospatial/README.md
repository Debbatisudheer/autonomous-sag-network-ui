# Phase 26 geospatial data

The project now supports real geospatial ingestion through explicit adapters rather than embedding live service results into the simulation core.

## Supported sources

- OpenStreetMap Nominatim: low-rate textual geocoding/search through `NominatimClient`.
- GeoJSON: deterministic offline ingestion of point features with provenance metadata.
- USGS 3DEP EPQS: explicit point-elevation adapter for supported US locations.

The bundled `ground-reference-india.geojson` is a deterministic city-reference fixture for offline regression tests. Its points are geographic reference locations, **not claims that telecommunications towers or radio sites exist at those coordinates**.

For real OSM ground-infrastructure ingestion, query an OSM/Overpass-derived GeoJSON or other OSM extract and preserve the source URI, feature ID, tags, and attribution in `GroundSiteRecord` / `GroundSiteDataset`.

OpenStreetMap data requires attribution and is distributed under the ODbL. Nominatim is intended for low-rate search/geocoding; production bulk extraction should use appropriate OSM data-download/Overpass infrastructure rather than hammering the public geocoder.
