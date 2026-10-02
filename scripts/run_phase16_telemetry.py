from __future__ import annotations

import json

from sag_network.digital_twin import DigitalTwin, DigitalTwinConfig
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.telemetry.bridge import TelemetryDigitalTwinBridge
from sag_network.telemetry.generator import generate_unified_telemetry
from sag_network.telemetry.models import TelemetryIngestionConfig
from sag_network.telemetry.state import TelemetryStateStore


def build_snapshot(timestamp_s: float) -> UnifiedNetworkSnapshot:
    candidate = UnifiedCandidate(
        resource_id="uav-a",
        domain=NetworkDomain.AIR,
        resource_type="uav",
        available=True,
        distance_m=10_000.0,
        rx_power_dbm=-65.0,
        noise_power_dbm=-95.0,
        sinr_db=20.0,
        link_margin_db=15.0,
        shannon_capacity_bps=150_000_000.0,
        estimated_capacity_bps=100_000_000.0,
        propagation_delay_ms=0.1,
        doppler_shift_hz=125.0,
        remaining_energy_wh=80.0,
    )
    return UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=50_000_000.0,
                allocated_capacity_bps=100_000_000.0,
                candidates=[candidate],
            )
        ],
    )


def main() -> None:
    snapshot = build_snapshot(180.0)
    twin = DigitalTwin(DigitalTwinConfig(twin_id="sag-twin", network_name="sag-demo"))
    twin_snapshot = twin.create_snapshot(
        snapshot_id="snapshot-001",
        timestamp_s=180.0,
        network_name="sag-demo",
        unified_state=snapshot,
    )

    batch = generate_unified_telemetry(snapshot)
    store = TelemetryStateStore(TelemetryIngestionConfig(stale_after_s=5.0))
    result = store.ingest_batch(batch)
    realtime = store.snapshot(timestamp_s=180.0)
    twin_link = TelemetryDigitalTwinBridge.link(
        telemetry_state=realtime,
        twin_snapshot=twin_snapshot,
    )
    stale_state = store.snapshot(timestamp_s=186.0)

    output = {
        "timestamp_s": realtime.timestamp_s,
        "generated_records": len(batch.records),
        "accepted_records": result.accepted_count,
        "rejected_records": result.rejected_count,
        "state_samples": realtime.sample_count,
        "stale_samples_at_180s": realtime.stale_sample_count,
        "stale_samples_at_186s": stale_state.stale_sample_count,
        "twin_snapshot_id": twin_link.twin_snapshot_id,
        "twin_alignment_timestamp_s": twin_link.telemetry_timestamp_s,
        "metrics": sorted({sample.metric.value for sample in realtime.samples}),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
