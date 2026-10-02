# SAG Network v2.0.0 — Live Showcase Runbook

This package is a presentation layer around the frozen SAG Network v2.0.0 codebase.

## Start

Double-click:

`START_SAG_DEMO.bat`

The browser opens automatically at:

`http://127.0.0.1:8765`

Keep the server window open while presenting.

## Recommended presentation sequence

1. Leave **Deterministic Synthetic** selected.
2. Start the **Run Live Demo**.
3. Show the real network state, serving resources, candidate set, telemetry/control health, autonomous pipeline, current decision, link-margin history, and event timeline.
4. Open **Regional** to show the exact local Ground/Air/User geometry.
5. Return to the main view and open **Resilience**.
6. Run **Run Resilience Campaign** to show the actual Phase 78 campaign.

## Evidence labels

The UI explicitly distinguishes software execution from physical deployment. It should be presented as a software/deterministic/public-data showcase, not as a claim of physical RF measurement or external-network mutation.

## Stop

Close the server window with `Ctrl+C`, or run `STOP_SAG_DEMO.bat`.

## Architecture

`src/` and `data/` are the SAG project execution source and data.

`showcase/` is the UI and thin demo adapter.

The frozen SAG v2.0.0 core is not replaced by this showcase layer.
