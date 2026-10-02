from __future__ import annotations

import pytest
from pydantic import ValidationError

from sag_network.decision.models import DecisionPriority
from sag_network.domain.unified import NetworkDomain
from sag_network.edge.coordinator import DistributedArchitectureEngine
from sag_network.edge.messaging import InMemoryMessageBroker
from sag_network.edge.models import (
    DistributedArchitectureConfig,
    DistributedTask,
    DistributedTaskType,
    EdgeCapability,
    EdgeFabricSnapshot,
    EdgeLink,
    EdgeNode,
    EdgeNodeHealth,
    EdgeNodeType,
    StateReplica,
)
from sag_network.edge.pipeline import build_pipeline_tasks
from sag_network.edge.placement import EdgeTaskPlacementEngine
from sag_network.edge.state import DistributedStateStore


def _fabric() -> EdgeFabricSnapshot:
    return EdgeFabricSnapshot(
        timestamp_s=10.0,
        nodes=[
            EdgeNode(
                node_id="ground-edge",
                node_type=EdgeNodeType.GROUND_EDGE,
                domain=NetworkDomain.GROUND,
                capabilities=list(EdgeCapability),
                network_latency_ms=5.0,
                processing_latency_ms=2.0,
            ),
            EdgeNode(
                node_id="air-edge",
                node_type=EdgeNodeType.AIR_EDGE,
                domain=NetworkDomain.AIR,
                capabilities=[EdgeCapability.TELEMETRY_INGESTION, EdgeCapability.PREDICTION],
                network_latency_ms=2.0,
                processing_latency_ms=1.0,
            ),
            EdgeNode(
                node_id="central",
                node_type=EdgeNodeType.CENTRAL_CONTROLLER,
                capabilities=list(EdgeCapability),
                network_latency_ms=30.0,
                processing_latency_ms=5.0,
            ),
        ],
        links=[
            EdgeLink(
                source_node_id="ground-edge",
                target_node_id="central",
                latency_ms=20.0,
                bandwidth_mbps=1000.0,
            )
        ],
    )


def _task(task_type: DistributedTaskType = DistributedTaskType.PREDICTION) -> DistributedTask:
    return DistributedTask(
        task_id="task-1",
        task_type=task_type,
        source_id="uav-a:user-01",
        timestamp_s=10.0,
        priority=DecisionPriority.HIGH,
        required_capabilities=[EdgeCapability.PREDICTION],
    )


def test_fabric_rejects_duplicate_nodes() -> None:
    node = EdgeNode(node_id="n1", node_type=EdgeNodeType.GROUND_EDGE)
    with pytest.raises(ValidationError):
        EdgeFabricSnapshot(timestamp_s=0, nodes=[node, node])


def test_fabric_rejects_unknown_link_nodes() -> None:
    with pytest.raises(ValidationError):
        EdgeFabricSnapshot(
            timestamp_s=0,
            nodes=[EdgeNode(node_id="n1", node_type=EdgeNodeType.GROUND_EDGE)],
            links=[EdgeLink(source_node_id="n1", target_node_id="n2", latency_ms=1, bandwidth_mbps=1)],
        )


def test_placement_prefers_lower_latency_when_domain_equal() -> None:
    fabric = _fabric()
    engine = EdgeTaskPlacementEngine()
    placement = engine.place(_task(), fabric)
    assert placement.feasible
    assert placement.node_id == "air-edge"


def test_placement_respects_capabilities() -> None:
    task = _task(DistributedTaskType.OPTIMIZATION).model_copy(
        update={"required_capabilities": [EdgeCapability.OPTIMIZATION]}
    )
    placement = EdgeTaskPlacementEngine().place(task, _fabric())
    assert placement.node_id == "ground-edge"


def test_placement_rejects_overloaded_node() -> None:
    node = EdgeNode(
        node_id="busy",
        node_type=EdgeNodeType.AIR_EDGE,
        capabilities=[EdgeCapability.PREDICTION],
        cpu_load_ratio=0.95,
    )
    fabric = EdgeFabricSnapshot(timestamp_s=0, nodes=[node])
    placement = EdgeTaskPlacementEngine(
        DistributedArchitectureConfig(maximum_node_cpu_load_ratio=0.9)
    ).place(_task(), fabric)
    assert not placement.feasible


def test_state_store_accepts_new_replica() -> None:
    store = DistributedStateStore()
    replica = StateReplica(
        state_key="network",
        source_node_id="edge-a",
        timestamp_s=1,
        version=0,
        state_hash="a" * 64,
    )
    assert store.upsert(replica)
    assert store.get("network") == replica


def test_state_store_rejects_older_version() -> None:
    store = DistributedStateStore()
    newer = StateReplica(
        state_key="network", source_node_id="edge-a", timestamp_s=2, version=2, state_hash="a" * 64
    )
    older = newer.model_copy(update={"timestamp_s": 3, "version": 1, "state_hash": "b" * 64})
    assert store.upsert(newer)
    assert not store.upsert(older)


def test_state_store_converges_identical_replicas() -> None:
    store = DistributedStateStore()
    for node_id in ["edge-a", "edge-b"]:
        assert store.upsert(
            StateReplica(
                state_key="network",
                source_node_id=node_id,
                timestamp_s=2,
                version=1,
                state_hash="a" * 64,
            )
        )
    assert store.is_converged("network")
    assert len(store.replicas("network")) == 2


def test_message_hash_and_id_are_deterministic() -> None:
    broker = InMemoryMessageBroker()
    m1 = broker.create_message(
        source_node_id="a",
        destination_node_id="b",
        topic="prediction",
        timestamp_s=10,
        priority=DecisionPriority.HIGH,
        payload={"x": 1, "y": 2},
    )
    m2 = broker.create_message(
        source_node_id="a",
        destination_node_id="b",
        topic="prediction",
        timestamp_s=10,
        priority=DecisionPriority.HIGH,
        payload={"y": 2, "x": 1},
    )
    assert m1.message_id == m2.message_id
    assert m1.payload_hash == m2.payload_hash


def test_message_broker_delivers_fresh_messages() -> None:
    broker = InMemoryMessageBroker()
    message = broker.create_message(
        source_node_id="a",
        destination_node_id="b",
        topic="telemetry",
        timestamp_s=10,
        priority=DecisionPriority.MEDIUM,
        payload={"value": 4},
    )
    broker.publish(message)
    delivered = broker.consume("b", now_s=12)
    assert len(delivered) == 1
    assert delivered[0].delivered


def test_message_broker_drops_expired_messages() -> None:
    broker = InMemoryMessageBroker()
    broker.publish(
        broker.create_message(
            source_node_id="a",
            destination_node_id="b",
            topic="telemetry",
            timestamp_s=10,
            priority=DecisionPriority.LOW,
            payload={"value": 4},
            ttl_s=1,
        )
    )
    assert broker.consume("b", now_s=12) == []


def test_pipeline_builds_all_required_stages() -> None:
    tasks = build_pipeline_tasks(timestamp_s=10, source_id="network")
    assert [task.task_type for task in tasks] == list(DistributedTaskType)


def test_pipeline_respects_unique_ids() -> None:
    tasks = build_pipeline_tasks(timestamp_s=10, source_id="network")
    assert len({task.task_id for task in tasks}) == len(tasks)


def test_coordinator_places_and_executes_tasks() -> None:
    engine = DistributedArchitectureEngine()
    report, fabric = engine.run_cycle(timestamp_s=10, fabric=_fabric(), tasks=[_task()])
    assert report.results[0].completed
    assert report.placements[0].node_id == "air-edge"
    assert fabric.nodes[1].queued_tasks == 1


def test_coordinator_replicates_state_to_multiple_nodes() -> None:
    engine = DistributedArchitectureEngine()
    report, _ = engine.run_cycle(
        timestamp_s=10,
        fabric=_fabric(),
        tasks=[],
        state_payloads={"network": {"source": "network", "value": 1}},
        replica_node_ids=["ground-edge", "central"],
    )
    assert report.replicated_state_count == 2
    assert engine.state_store.is_converged("network")


def test_coordinator_rejects_task_without_capacity() -> None:
    busy = EdgeNode(
        node_id="busy",
        node_type=EdgeNodeType.AIR_EDGE,
        capabilities=[EdgeCapability.PREDICTION],
        queued_tasks=1,
        queue_capacity=1,
    )
    fabric = EdgeFabricSnapshot(timestamp_s=10, nodes=[busy])
    report, _ = DistributedArchitectureEngine().run_cycle(timestamp_s=10, fabric=fabric, tasks=[_task()])
    assert report.rejected_task_ids == ["task-1"]
    assert not report.results[0].accepted


def test_offline_nodes_are_excluded() -> None:
    node = EdgeNode(
        node_id="offline",
        node_type=EdgeNodeType.AIR_EDGE,
        capabilities=[EdgeCapability.PREDICTION],
        health=EdgeNodeHealth.OFFLINE,
        active=False,
    )
    placement = EdgeTaskPlacementEngine().place(
        _task(), EdgeFabricSnapshot(timestamp_s=0, nodes=[node])
    )
    assert not placement.feasible
