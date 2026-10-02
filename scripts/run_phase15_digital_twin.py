from __future__ import annotations

import json

from sag_network.digital_twin import DigitalTwin, DigitalTwinConfig
from sag_network.domain.resource import (
    ResourceUtilization,
    SpectrumAllocation,
    SpectrumSchedulingSnapshot,
)
from sag_network.domain.topology import (
    NetworkTopology,
    TopologyLink,
    TopologyNode,
    TopologyNodeType,
)
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)


def build_unified_state(timestamp_s: float, sinr_db: float) -> UnifiedNetworkSnapshot:
    candidate = UnifiedCandidate(
        resource_id="uav-a",
        domain=NetworkDomain.AIR,
        resource_type="uav",
        available=True,
        distance_m=1200.0,
        rx_power_dbm=-69.0,
        noise_power_dbm=-100.0,
        sinr_db=sinr_db,
        link_margin_db=sinr_db - 5.0,
        shannon_capacity_bps=100_000_000.0,
        estimated_capacity_bps=80_000_000.0,
        propagation_delay_ms=0.008,
    )
    return UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=50_000_000.0,
                allocated_capacity_bps=80_000_000.0,
                candidates=[candidate],
            )
        ],
    )


def build_topology() -> NetworkTopology:
    return NetworkTopology(
        name="sag-demo-topology",
        nodes=[
            TopologyNode(node_id="user-01", node_type=TopologyNodeType.USER, domain="ground"),
            TopologyNode(node_id="uav-a", node_type=TopologyNodeType.UAV, domain="air"),
            TopologyNode(node_id="core", node_type=TopologyNodeType.CORE, domain="ground"),
        ],
        links=[
            TopologyLink(
                link_id="user-uav",
                source_id="user-01",
                target_id="uav-a",
                capacity_bps=80_000_000.0,
                latency_ms=1.0,
                loss_rate=0.0,
            ),
            TopologyLink(
                link_id="uav-core",
                source_id="uav-a",
                target_id="core",
                capacity_bps=100_000_000.0,
                latency_ms=2.0,
                loss_rate=0.0,
            ),
        ],
    )


def build_spectrum(timestamp_s: float, used_blocks: int) -> SpectrumSchedulingSnapshot:
    return SpectrumSchedulingSnapshot(
        timestamp_s=timestamp_s,
        allocations=[
            SpectrumAllocation(
                flow_id="flow-01",
                user_id="user-01",
                admitted=True,
                resource_id="uav-a",
                requested_bps=50_000_000.0,
                required_bps=50_000_000.0,
                allocated_bps=50_000_000.0,
                resource_blocks=used_blocks,
                allocated_bandwidth_hz=used_blocks * 1_000_000.0,
                reason="spectrum_requirements_satisfied",
            )
        ],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a",
                total_resource_blocks=20,
                used_resource_blocks=used_blocks,
                free_resource_blocks=20 - used_blocks,
                utilization_ratio=used_blocks / 20.0,
                scheduled_capacity_bps=50_000_000.0,
                remaining_capacity_bps=30_000_000.0,
            )
        ],
    )


if __name__ == "__main__":
    twin = DigitalTwin(
        DigitalTwinConfig(
            twin_id="sag-twin",
            network_name="autonomous-sag-network",
            history_limit=10,
        )
    )
    first = twin.create_snapshot(
        snapshot_id="snapshot-0001",
        timestamp_s=0.0,
        network_name="autonomous-sag-network",
        unified_state=build_unified_state(0.0, 12.0),
        topology=build_topology(),
        spectrum_state=build_spectrum(0.0, 5),
        source="simulation",
        metadata={"scenario": "digital-twin-baseline"},
    )
    second = twin.create_snapshot(
        snapshot_id="snapshot-0002",
        timestamp_s=1.0,
        network_name="autonomous-sag-network",
        unified_state=build_unified_state(1.0, 8.0),
        topology=build_topology(),
        spectrum_state=build_spectrum(1.0, 7),
        source="simulation",
        metadata={"scenario": "digital-twin-baseline"},
    )
    twin.sync_many((first, second))
    delta = twin.delta(first, second)

    output = {
        "twin_id": twin.config.twin_id,
        "latest_snapshot_id": twin.latest.snapshot_id if twin.latest else None,
        "history_size": len(twin.history),
        "latest_state_hash": twin.latest.state_hash if twin.latest else None,
        "delta": delta.model_dump(mode="json"),
    }
    print(json.dumps(output, indent=2))
