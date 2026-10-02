from __future__ import annotations

from datetime import datetime, UTC
from typing import Any


def telemetry_event(event_type: str, payload: dict[str, Any], timestamp_s: float) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "simulation_time_s": timestamp_s,
        "emitted_at_utc": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
