from __future__ import annotations

from sag_network.decision.models import DecisionPriority
from sag_network.edge.models import DistributedTask, DistributedTaskType, EdgeCapability


def build_pipeline_tasks(*, timestamp_s: float, source_id: str) -> list[DistributedTask]:
    """Build one deterministic distributed workload graph for an autonomous cycle."""
    stages = [
        ("telemetry", DistributedTaskType.TELEMETRY_INGESTION, EdgeCapability.TELEMETRY_INGESTION, DecisionPriority.MEDIUM),
        ("aggregate", DistributedTaskType.STATE_AGGREGATION, EdgeCapability.STATE_AGGREGATION, DecisionPriority.MEDIUM),
        ("predict", DistributedTaskType.PREDICTION, EdgeCapability.PREDICTION, DecisionPriority.HIGH),
        ("decide", DistributedTaskType.DECISION, EdgeCapability.DECISION, DecisionPriority.HIGH),
        ("optimize", DistributedTaskType.OPTIMIZATION, EdgeCapability.OPTIMIZATION, DecisionPriority.CRITICAL),
        ("recover", DistributedTaskType.RECOVERY, EdgeCapability.RECOVERY, DecisionPriority.CRITICAL),
        ("twin", DistributedTaskType.DIGITAL_TWIN_SYNC, EdgeCapability.DIGITAL_TWIN_SYNC, DecisionPriority.HIGH),
    ]
    return [
        DistributedTask(
            task_id=f"{stage}-{source_id}-{int(timestamp_s)}",
            task_type=task_type,
            source_id=source_id,
            timestamp_s=timestamp_s,
            priority=priority,
            required_capabilities=[capability],
            expected_processing_ms=2.0 if task_type in {
                DistributedTaskType.PREDICTION,
                DistributedTaskType.OPTIMIZATION,
            } else 1.0,
            maximum_latency_ms=50.0 if task_type in {
                DistributedTaskType.RECOVERY,
                DistributedTaskType.OPTIMIZATION,
            } else 100.0,
        )
        for stage, task_type, capability, priority in stages
    ]


__all__ = ["build_pipeline_tasks"]
