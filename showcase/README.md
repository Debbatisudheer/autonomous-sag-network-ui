# SAG Network v2.0.0 — Live UI Showcase v0.7

This showcase is a presentation layer around the frozen SAG v2.0.0 codebase. The `src/` implementation is executed by the showcase server; the browser visualizes returned project state/events.

## Run

From the package root:

```powershell
python showcase\server.py
```

Open `http://127.0.0.1:8765`.

If that port is already in use:

```powershell
$env:SAG_SHOWCASE_PORT=8775
python showcase\server.py
```

Then open `http://127.0.0.1:8775`.

## Evidence boundary

The dashboard distinguishes synthetic fixture, public ephemeris, and localhost modes. It does not claim physical RF measurement, physical hardware actuation, or external-network mutation.

## v0.7 map view

The default **Operational Map** uses a bundled static geographic basemap for geographic context. Network nodes, links, user state, serving resources, and orbit data are rendered from the actual project runtime.


### v1.2
Global and 3D views use a clearly labeled aggregate for the tightly co-located local fixture; Regional view remains the detailed exact-coordinate inspection view.
