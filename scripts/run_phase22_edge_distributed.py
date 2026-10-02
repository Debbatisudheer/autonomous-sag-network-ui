from __future__ import annotations

import json

from sag_network.decision.models import DecisionPriority
from sag_network.domain.unified import NetworkDomain
from sag_network.edge.coordinator import DistributedArchitectureEngine
from sag_network.edge.messaging import InMemoryMessageBroker
from sag_network.edge.models import (
    EdgeCapability,
    EdgeFabricSnapshot,
    EdgeLink,
    EdgeNode,
    EdgeNodeType,
)
from sag_network.edge.pipeline import build_pipeline_tasks


def main() -> None:
    fabric = EdgeFabricSnapshot(
        timestamp_s=30.0,
        nodes=[
            EdgeNode(
                node_id="ground-edge-a",
                node_type=EdgeNodeType.GROUND_EDGE,
                domain=NetworkDomain.GROUND,
                capabilities=[
                    EdgeCapability.TELEMETRY_INGESTION,
                    EdgeCapability.STATE_AGGREGATION,
                    EdgeCapability.DIGITAL_TWIN_SYNC,
                ],
                network_latency_ms=4.0,
                processing_latency_ms=2.0,
            ),
            EdgeNode(
                node_id="air-edge-a",
                node_type=EdgeNodeType.AIR_EDGE,
                domain=NetworkDomain.AIR,
                capabilities=[
                    EdgeCapability.TELEMETRY_INGESTION,
                    EdgeCapability.PREDICTION,
                ],
                network_latency_ms=2.0,
                processing_latency_ms=1.0,
            ),
            EdgeNode(
                node_id="regional-a",
                node_type=EdgeNodeType.REGIONAL_CONTROLLER,
                capabilities=[
                    EdgeCapability.PREDICTION,
                    EdgeCapability.DECISION,
                    EdgeCapability.OPTIMIZATION,
                    EdgeCapability.RECOVERY,
                ],
                network_latency_ms=6.0,
                processing_latency_ms=3.0,
            ),
            EdgeNode(
                node_id="central-a",
                node_type=EdgeNodeType.CENTRAL_CONTROLLER,
                capabilities=list(EdgeCapability),
                network_latency_ms=25.0,
                processing_latency_ms=5.0,
            ),
        ],
        links=[
            EdgeLink(
                source_node_id="air-edge-a",
                target_node_id="regional-a",
                latency_ms=8.0,
                bandwidth_mbps=500.0,
            ),
            EdgeLink(
                source_node_id="regional-a",
                target_node_id="central-a",
                latency_ms=18.0,
                bandwidth_mbps=1000.0,
            ),
        ],
    )
    engine = DistributedArchitectureEngine()
    tasks = build_pipeline_tasks(timestamp_s=30.0, source_id="uav-a:user-01")
    report, updated_fabric = engine.run_cycle(
        timestamp_s=30.0,
        fabric=fabric,
        tasks=tasks,
        state_payloads={"autonomous-cycle": {"source_node_id": "regional-a", "stage": "phase22"}},
        replica_node_ids=["regional-a", "central-a"],
    )

    broker = InMemoryMessageBroker()
    message = broker.create_message(
        source_node_id="air-edge-a",
        destination_node_id="regional-a",
        topic="telemetry.state",
        timestamp_s=30.0,
        priority=DecisionPriority.HIGH,
        payload={"source": "uav-a:user-01", "sample_count": 9},
    )
    broker.publish(message)
    delivered = broker.consume("regional-a", now_s=31.0)

    print(
        json.dumps(
            {
                "timestamp_s": 30.0,
                "fabric_nodes": len(fabric.nodes),
                "tasks": len(tasks),
                "placements": [
                    {"task_id": p.task_id, "node_id": p.node_id, "latency_ms": p.estimated_latency_ms}
                    for p in report.placements
                ],
                "completed_tasks": sum(result.completed for result in report.results),
                "rejected_tasks": report.rejected_task_ids,
                "replicated_state_count": report.replicated_state_count,
                "state_converged": engine.state_store.is_converged("autonomous-cycle"),
                "message_delivered": len(delivered),
                "updated_queue_depths": {
                    node.node_id: node.queued_tasks for node in updated_fabric.nodes if node.queued_tasks
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
