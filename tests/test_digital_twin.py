from __future__ import annotations

import pytest

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


def candidate(*, resource_id: str, sinr_db: float = 10.0) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.AIR,
        resource_type="uav",
        available=True,
        distance_m=1000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=sinr_db,
        link_margin_db=sinr_db - 5.0,
        shannon_capacity_bps=100_000_000.0,
        estimated_capacity_bps=80_000_000.0,
        propagation_delay_ms=0.01,
    )


def unified_state(*, timestamp_s: float, sinr_db: float = 10.0) -> UnifiedNetworkSnapshot:
    return UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=50_000_000.0,
                allocated_capacity_bps=80_000_000.0,
                candidates=[candidate(resource_id="uav-a", sinr_db=sinr_db)],
            )
        ],
    )


def topology() -> NetworkTopology:
    return NetworkTopology(
        name="sag-topology",
        nodes=[
            TopologyNode(node_id="user-01", node_type=TopologyNodeType.USER, domain="ground"),
            TopologyNode(node_id="uav-a", node_type=TopologyNodeType.UAV, domain="air"),
        ],
        links=[
            TopologyLink(
                link_id="user-uav",
                source_id="user-01",
                target_id="uav-a",
                capacity_bps=80_000_000.0,
                latency_ms=1.0,
                loss_rate=0.0,
            )
        ],
    )


def spectrum_state(*, timestamp_s: float, used_blocks: int) -> SpectrumSchedulingSnapshot:
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
                remaining_capacity_bps=80_000_000.0 - 50_000_000.0,
            )
        ],
    )


def make_twin(*, history_limit: int = 100) -> DigitalTwin:
    return DigitalTwin(
        DigitalTwinConfig(
            twin_id="twin-01",
            network_name="sag-demo",
            history_limit=history_limit,
        )
    )


def make_snapshot(
    twin: DigitalTwin,
    *,
    snapshot_id: str,
    timestamp_s: float,
    sinr_db: float = 10.0,
    used_blocks: int = 5,
):
    return twin.create_snapshot(
        snapshot_id=snapshot_id,
        timestamp_s=timestamp_s,
        network_name="sag-demo",
        unified_state=unified_state(timestamp_s=timestamp_s, sinr_db=sinr_db),
        topology=topology(),
        spectrum_state=spectrum_state(timestamp_s=timestamp_s, used_blocks=used_blocks),
    )


def test_create_snapshot_computes_stable_hash() -> None:
    twin = make_twin()
    first = make_snapshot(twin, snapshot_id="s-01", timestamp_s=0.0)
    second = make_snapshot(twin, snapshot_id="s-01", timestamp_s=0.0)
    assert first.state_hash == second.state_hash
    assert len(first.state_hash) == 64


def test_snapshot_hash_detects_tampering() -> None:
    twin = make_twin()
    snapshot = make_snapshot(twin, snapshot_id="s-01", timestamp_s=0.0)
    tampered = snapshot.model_copy(update={"network_name": "tampered"})
    with pytest.raises(ValueError, match="state_hash"):
        twin.sync(tampered)


def test_sync_appends_and_exposes_latest() -> None:
    twin = make_twin()
    snapshot = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0)
    twin.sync(snapshot)
    assert twin.latest == snapshot
    assert twin.history == (snapshot,)


def test_monotonic_time_is_enforced() -> None:
    twin = make_twin()
    twin.sync(make_snapshot(twin, snapshot_id="s-01", timestamp_s=10.0))
    with pytest.raises(ValueError, match="timestamp"):
        twin.sync(make_snapshot(twin, snapshot_id="s-00", timestamp_s=9.0))


def test_history_limit_evicts_oldest_snapshot() -> None:
    twin = make_twin(history_limit=2)
    snapshots = [
        make_snapshot(twin, snapshot_id=f"s-{index}", timestamp_s=float(index))
        for index in range(3)
    ]
    twin.sync_many(snapshots)
    assert [item.snapshot_id for item in twin.history] == ["s-1", "s-2"]


def test_snapshot_at_or_before_returns_latest_eligible_snapshot() -> None:
    twin = make_twin()
    snapshots = [
        make_snapshot(twin, snapshot_id=f"s-{index}", timestamp_s=float(index))
        for index in range(3)
    ]
    twin.sync_many(snapshots)
    assert twin.snapshot_at_or_before(1.5) == snapshots[1]
    assert twin.snapshot_at_or_before(0.0) == snapshots[0]
    assert twin.snapshot_at_or_before(-1.0) is None


def test_delta_identifies_changed_candidate_and_spectrum_state() -> None:
    twin = make_twin()
    previous = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0, sinr_db=10.0, used_blocks=5)
    current = make_snapshot(twin, snapshot_id="s-02", timestamp_s=2.0, sinr_db=7.0, used_blocks=6)
    delta = twin.delta(previous, current)
    assert delta.timestamp_delta_s == 1.0
    assert delta.changed_user_ids == ["user-01"]
    assert delta.changed_candidate_ids == ["uav-a"]
    assert delta.changed_spectrum_resource_ids == ["uav-a"]
    assert delta.has_changes is True


def test_delta_detects_topology_changes() -> None:
    twin = make_twin()
    previous = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0)
    changed_topology = topology().model_copy(
        update={"nodes": [*topology().nodes, TopologyNode(
            node_id="core",
            node_type=TopologyNodeType.CORE,
            domain="ground",
        )]}
    )
    current = twin.create_snapshot(
        snapshot_id="s-02",
        timestamp_s=2.0,
        network_name="sag-demo",
        unified_state=unified_state(timestamp_s=2.0),
        topology=changed_topology,
        spectrum_state=spectrum_state(timestamp_s=2.0, used_blocks=5),
    )
    delta = twin.delta(previous, current)
    assert delta.changed_topology_node_ids == ["core"]


def test_identical_snapshots_have_no_state_delta() -> None:
    twin = make_twin()
    previous = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0)
    current = make_snapshot(twin, snapshot_id="s-02", timestamp_s=1.0)
    delta = twin.delta(previous, current)
    assert delta.has_changes is False


def test_delta_rejects_reversed_time() -> None:
    twin = make_twin()
    previous = make_snapshot(twin, snapshot_id="s-02", timestamp_s=2.0)
    current = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0)
    with pytest.raises(ValueError, match="precede"):
        twin.delta(previous, current)


def test_snapshot_rejects_unsynchronized_component_timestamp() -> None:
    twin = make_twin()
    invalid_unified = unified_state(timestamp_s=2.0)
    with pytest.raises(ValueError, match="unified_state timestamp"):
        twin.create_snapshot(
            snapshot_id="s-01",
            timestamp_s=1.0,
            network_name="sag-demo",
            unified_state=invalid_unified,
        )


def test_snapshot_rejects_duplicate_id() -> None:
    twin = make_twin()
    snapshot = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0)
    twin.sync(snapshot)
    with pytest.raises(ValueError, match="snapshot_id already exists"):
        twin.sync(snapshot)


def test_network_name_is_bound_to_configured_twin() -> None:
    twin = make_twin()
    snapshot = make_snapshot(twin, snapshot_id="s-01", timestamp_s=1.0)
    invalid = snapshot.model_copy(update={"network_name": "other-network", "state_hash": "0" * 64})
    # Build a valid hash for the altered snapshot so the network-name check is exercised.
    invalid = invalid.model_copy(update={"state_hash": twin.compute_state_hash(invalid)})
    with pytest.raises(ValueError, match="network_name"):
        twin.sync(invalid)


def test_optional_components_can_be_omitted() -> None:
    twin = make_twin()
    snapshot = twin.create_snapshot(
        snapshot_id="s-01",
        timestamp_s=1.0,
        network_name="sag-demo",
        unified_state=unified_state(timestamp_s=1.0),
    )
    twin.sync(snapshot)
    assert snapshot.topology is None
    assert snapshot.spectrum_state is None
    assert snapshot.interference_evaluations == []


def test_metadata_and_source_are_preserved() -> None:
    twin = make_twin()
    snapshot = twin.create_snapshot(
        snapshot_id="s-01",
        timestamp_s=1.0,
        network_name="sag-demo",
        unified_state=unified_state(timestamp_s=1.0),
        source="telemetry",
        metadata={"scenario": "handover-test", "region": "test"},
    )
    assert snapshot.source == "telemetry"
    assert snapshot.metadata == {"scenario": "handover-test", "region": "test"}
