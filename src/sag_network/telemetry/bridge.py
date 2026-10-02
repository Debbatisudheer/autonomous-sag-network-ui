from __future__ import annotations

from sag_network.digital_twin.models import DigitalTwinSnapshot
from sag_network.telemetry.models import RealTimeStateSnapshot, TelemetryTwinLink


class TelemetryDigitalTwinBridge:
    """Explicit boundary between real-time telemetry state and digital-twin snapshots."""

    @staticmethod
    def link(
        *,
        telemetry_state: RealTimeStateSnapshot,
        twin_snapshot: DigitalTwinSnapshot,
    ) -> TelemetryTwinLink:
        if telemetry_state.timestamp_s != twin_snapshot.timestamp_s:
            raise ValueError("telemetry state timestamp must match digital twin snapshot timestamp")
        return TelemetryTwinLink(
            twin_snapshot_id=twin_snapshot.snapshot_id,
            twin_timestamp_s=twin_snapshot.timestamp_s,
            telemetry_timestamp_s=telemetry_state.timestamp_s,
            sample_count=telemetry_state.sample_count,
            stale_sample_count=telemetry_state.stale_sample_count,
        )
