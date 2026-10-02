from __future__ import annotations

import hashlib
import json

from sag_network.edge.executor import apply_queue_update, execute_task
from sag_network.edge.models import (
    DistributedArchitectureConfig,
    DistributedCycleReport,
    DistributedTask,
    EdgeFabricSnapshot,
    StateReplica,
)
from sag_network.edge.placement import EdgeTaskPlacementEngine
from sag_network.edge.state import DistributedStateStore


def _state_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DistributedArchitectureEngine:
    """Coordinates task placement and replicated state across the compute fabric."""

    def __init__(self, config: DistributedArchitectureConfig | None = None) -> None:
        self.config = config or DistributedArchitectureConfig()
        self.placement = EdgeTaskPlacementEngine(self.config)
        self.state_store = DistributedStateStore(self.config.state_config)

    def run_cycle(
        self,
        *,
        timestamp_s: float,
        fabric: EdgeFabricSnapshot,
        tasks: list[DistributedTask],
        state_payloads: dict[str, dict[str, object]] | None = None,
        replica_node_ids: list[str] | None = None,
    ) -> tuple[DistributedCycleReport, EdgeFabricSnapshot]:
        tasks = sorted(tasks, key=lambda item: (-_priority_rank(item.priority.value), item.task_id))[
            : self.config.maximum_tasks_per_cycle
        ]
        working_fabric = fabric
        placements = []
        results = []
        rejected: list[str] = []
        for task in tasks:
            placement = self.placement.place(task, working_fabric)
            placements.append(placement)
            result = execute_task(task=task, placement=placement, timestamp_s=timestamp_s)
            results.append(result)
            if not placement.feasible:
                rejected.append(task.task_id)
                continue
            working_fabric = apply_queue_update(working_fabric, placement, task)

        replicas = 0
        if state_payloads:
            targets = replica_node_ids or ["regional-controller"]
            for key in sorted(state_payloads):
                payload = state_payloads[key]
                state_hash = _state_hash(payload)
                current = self.state_store.get(key)
                version = 0 if current is None else current.version + 1
                for node_id in sorted(set(targets)):
                    if node_id not in {node.node_id for node in fabric.nodes}:
                        continue
                    replica = StateReplica(
                        state_key=key,
                        source_node_id=node_id,
                        timestamp_s=timestamp_s,
                        version=version,
                        state_hash=state_hash,
                    )
                    if self.state_store.upsert(replica):
                        replicas += 1

        return (
            DistributedCycleReport(
                timestamp_s=timestamp_s,
                placements=placements,
                results=results,
                replicated_state_count=replicas,
                rejected_task_ids=rejected,
            ),
            working_fabric,
        )


def _priority_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(value, -1)


__all__ = ["DistributedArchitectureEngine"]
