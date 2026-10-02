from __future__ import annotations

from sag_network.edge.models import (
    DistributedArchitectureConfig,
    DistributedTask,
    EdgeFabricSnapshot,
    EdgeNode,
    EdgeNodeHealth,
    TaskPlacement,
)


def _available_cpu(node: EdgeNode) -> int:
    return max(0, int(node.cpu_capacity_millicores * (1.0 - node.cpu_load_ratio)))


def _available_memory(node: EdgeNode) -> int:
    return max(0, int(node.memory_capacity_mb * (1.0 - node.memory_load_ratio)))


def _node_score(node: EdgeNode, task: DistributedTask) -> tuple[float, float, float, str]:
    domain_penalty = 0.0
    if task.preferred_domain is not None and node.domain is not task.preferred_domain:
        domain_penalty = 10.0
    load_penalty = node.cpu_load_ratio + node.memory_load_ratio
    latency = node.network_latency_ms + node.processing_latency_ms + task.expected_processing_ms
    return (domain_penalty + load_penalty, latency, node.queued_tasks, node.node_id)


class EdgeTaskPlacementEngine:
    """Deterministic scheduler for placing distributed tasks on the edge fabric."""

    def __init__(self, config: DistributedArchitectureConfig | None = None) -> None:
        self.config = config or DistributedArchitectureConfig()

    def candidates(self, task: DistributedTask, fabric: EdgeFabricSnapshot) -> list[EdgeNode]:
        nodes: list[EdgeNode] = []
        for node in fabric.nodes:
            if not node.active or node.health is EdgeNodeHealth.OFFLINE:
                continue
            if node.cpu_load_ratio > self.config.maximum_node_cpu_load_ratio:
                continue
            if node.memory_load_ratio > self.config.maximum_node_memory_load_ratio:
                continue
            if node.queued_tasks >= node.queue_capacity:
                continue
            if not set(task.required_capabilities).issubset(set(node.capabilities)):
                continue
            if _available_cpu(node) < task.cpu_required_millicores:
                continue
            if _available_memory(node) < task.memory_required_mb:
                continue
            latency = node.network_latency_ms + node.processing_latency_ms + task.expected_processing_ms
            if latency > min(task.maximum_latency_ms, self.config.maximum_task_latency_ms):
                continue
            nodes.append(node)
        return sorted(nodes, key=lambda node: _node_score(node, task))

    def place(self, task: DistributedTask, fabric: EdgeFabricSnapshot) -> TaskPlacement:
        options = self.candidates(task, fabric)
        if not options:
            return TaskPlacement(
                task_id=task.task_id,
                node_id="unassigned",
                feasible=False,
                estimated_latency_ms=0.0,
                cpu_headroom_millicores=0,
                memory_headroom_mb=0,
                placement_score=0.0,
                rationale="no eligible edge node satisfied capability, capacity, health, or latency constraints",
            )

        node = options[0]
        latency = node.network_latency_ms + node.processing_latency_ms + task.expected_processing_ms
        score = max(0.0, 100.0 - latency - 25.0 * (node.cpu_load_ratio + node.memory_load_ratio))
        if task.preferred_domain is not None and node.domain is not task.preferred_domain:
            score = max(0.0, score - 10.0)
        return TaskPlacement(
            task_id=task.task_id,
            node_id=node.node_id,
            feasible=True,
            estimated_latency_ms=latency,
            cpu_headroom_millicores=_available_cpu(node) - task.cpu_required_millicores,
            memory_headroom_mb=_available_memory(node) - task.memory_required_mb,
            placement_score=score,
            rationale=f"selected {node.node_id} using deterministic latency/load/domain-aware placement",
        )


__all__ = ["EdgeTaskPlacementEngine"]
