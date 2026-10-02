from __future__ import annotations

from sag_network.edge.models import (
    DistributedTask,
    DistributedTaskResult,
    EdgeFabricSnapshot,
    TaskPlacement,
)


def execute_task(
    *, task: DistributedTask, placement: TaskPlacement, timestamp_s: float
) -> DistributedTaskResult:
    if not placement.feasible:
        return DistributedTaskResult(
            task_id=task.task_id,
            node_id=placement.node_id,
            accepted=False,
            completed=False,
            timestamp_s=timestamp_s,
            latency_ms=0.0,
            reason=placement.rationale,
        )
    return DistributedTaskResult(
        task_id=task.task_id,
        node_id=placement.node_id,
        accepted=True,
        completed=True,
        timestamp_s=timestamp_s,
        latency_ms=placement.estimated_latency_ms,
        reason="simulation task completed on selected distributed node",
    )


def apply_queue_update(
    fabric: EdgeFabricSnapshot, placement: TaskPlacement, task: DistributedTask
) -> EdgeFabricSnapshot:
    """Return a new fabric snapshot with deterministic queue/load changes."""
    nodes = []
    for node in fabric.nodes:
        if node.node_id != placement.node_id or not placement.feasible:
            nodes.append(node)
            continue
        cpu_fraction = task.cpu_required_millicores / node.cpu_capacity_millicores
        memory_fraction = task.memory_required_mb / node.memory_capacity_mb
        nodes.append(
            node.model_copy(
                update={
                    "queued_tasks": min(node.queue_capacity, node.queued_tasks + 1),
                    "cpu_load_ratio": min(1.0, node.cpu_load_ratio + cpu_fraction),
                    "memory_load_ratio": min(1.0, node.memory_load_ratio + memory_fraction),
                }
            )
        )
    return fabric.model_copy(update={"nodes": nodes})


__all__ = ["apply_queue_update", "execute_task"]
