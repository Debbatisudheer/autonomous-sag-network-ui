# SAG Network v2.0.0 Live UI Showcase — v1.0

Map stability hardening release.

- Removed continuous requestAnimationFrame map redraw; map renders on actual state/events and explicit view/resize changes.
- Removed programmatic scrollIntoView workspace navigation.
- Operational map no longer resizes the canvas from inside its own draw routine.
- Canvas is absolutely positioned inside a fixed, size-contained map viewport.
- No changes to the SAG core under src/ or project data under data/.
