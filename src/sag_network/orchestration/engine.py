from __future__ import annotations

import hashlib
import json

from sag_network.orchestration.models import (
    OrchestrationDecision,
    OrchestrationNode,
    OrchestrationPlacement,
    OrchestrationReport,
    OrchestrationWorkload,
)


class EdgeResourceOrchestrator:
    """Deterministic admission and rebalance planner for edge workloads."""

    def __init__(self, *, maximum_utilization: float = 0.9) -> None:
        if not 0 < maximum_utilization <= 1:
            raise ValueError("maximum_utilization must be in (0, 1]")
        self.maximum_utilization = maximum_utilization

    def plan(
        self,
        *,
        timestamp_s: float,
        nodes: list[OrchestrationNode],
        workloads: list[OrchestrationWorkload],
        assignments: dict[str, str] | None = None,
    ) -> OrchestrationReport:
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")
        node_map = {node.node_id: node for node in nodes}
        if len(node_map) != len(nodes):
            raise ValueError("node ids must be unique")
        if len({workload.workload_id for workload in workloads}) != len(workloads):
            raise ValueError("workload ids must be unique")
        current = dict(assignments or {})
        if any(node_id not in node_map for node_id in current.values()):
            raise ValueError("assignments must reference known nodes")

        before = self._utilization(nodes)
        working = {
            node.node_id: [node.cpu_used_millicores, node.memory_used_mb]
            for node in nodes
        }
        placements: list[OrchestrationPlacement] = []
        rejected: list[str] = []
        moved: list[str] = []
        group_nodes: dict[str, set[str]] = {}

        ordered = sorted(workloads, key=lambda item: (-item.priority, item.workload_id))
        for workload in ordered:
            existing = current.get(workload.workload_id)
            candidates = self._candidates(workload, node_map, working, group_nodes)
            if existing in candidates:
                chosen = existing
                decision = OrchestrationDecision.KEEP
            elif candidates:
                chosen = min(
                    candidates,
                    key=lambda node_id: self._score(
                        workload, node_map[node_id], working[node_id]
                    ),
                )
                decision = (
                    OrchestrationDecision.REBALANCE
                    if existing is not None
                    else OrchestrationDecision.PLACE
                )
                if existing is not None:
                    moved.append(workload.workload_id)
            else:
                rejected.append(workload.workload_id)
                placements.append(
                    OrchestrationPlacement(
                        workload_id=workload.workload_id,
                        node_id="unassigned",
                        decision=OrchestrationDecision.REJECT,
                        cpu_headroom_millicores=0,
                        memory_headroom_mb=0,
                        placement_score=0.0,
                        rationale=(
                            "no healthy node satisfies capacity and anti-affinity constraints"
                        ),
                    )
                )
                continue

            usage = working[chosen]
            usage[0] += workload.cpu_millicores
            usage[1] += workload.memory_mb
            node = node_map[chosen]
            group = workload.anti_affinity_group
            if group is not None:
                group_nodes.setdefault(group, set()).add(chosen)
            cpu_headroom = node.cpu_capacity_millicores - usage[0]
            memory_headroom = node.memory_capacity_mb - usage[1]
            placements.append(
                OrchestrationPlacement(
                    workload_id=workload.workload_id,
                    node_id=chosen,
                    decision=decision,
                    cpu_headroom_millicores=cpu_headroom,
                    memory_headroom_mb=memory_headroom,
                    placement_score=self._placement_score(workload, node, usage),
                    rationale=(
                        f"{decision.value} using deterministic priority, capacity, "
                        "and anti-affinity policy"
                    ),
                )
            )

        after = self._utilization_from_usage(node_map, working)
        plan_payload = {
            "timestamp_s": timestamp_s,
            "placements": [item.model_dump(mode="json") for item in placements],
            "rejected": sorted(rejected),
            "moved": sorted(moved),
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                plan_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return OrchestrationReport(
            timestamp_s=timestamp_s,
            placements=placements,
            rejected_workload_ids=rejected,
            moved_workload_ids=moved,
            utilization_before=before,
            utilization_after=after,
            rebalance_required=bool(moved),
            plan_fingerprint=fingerprint,
        )

    def _candidates(
        self,
        workload: OrchestrationWorkload,
        nodes: dict[str, OrchestrationNode],
        usage: dict[str, list[int]],
        group_nodes: dict[str, set[str]],
    ) -> list[str]:
        candidates: list[str] = []
        for node_id, node in sorted(nodes.items()):
            if not node.healthy:
                continue
            cpu_after = usage[node_id][0] + workload.cpu_millicores
            memory_after = usage[node_id][1] + workload.memory_mb
            if cpu_after > node.cpu_capacity_millicores * self.maximum_utilization:
                continue
            if memory_after > node.memory_capacity_mb * self.maximum_utilization:
                continue
            if workload.anti_affinity_group and node_id in group_nodes.get(
                workload.anti_affinity_group, set()
            ):
                continue
            candidates.append(node_id)
        return candidates

    @staticmethod
    def _score(
        workload: OrchestrationWorkload,
        node: OrchestrationNode,
        usage: list[int],
    ) -> tuple[float, float, float, str]:
        cpu_ratio = usage[0] / node.cpu_capacity_millicores
        memory_ratio = usage[1] / node.memory_capacity_mb
        preference = 0.0 if workload.preferred_node_id == node.node_id else 1.0
        return (
            preference,
            max(cpu_ratio, memory_ratio),
            cpu_ratio + memory_ratio,
            node.node_id,
        )

    @classmethod
    def _placement_score(
        cls,
        workload: OrchestrationWorkload,
        node: OrchestrationNode,
        usage: list[int],
    ) -> float:
        preference, peak_ratio, aggregate_ratio, _ = cls._score(workload, node, usage)
        return max(
            0.0,
            100.0
            - 10.0 * preference
            - 50.0 * peak_ratio
            - 20.0 * aggregate_ratio,
        )

    @staticmethod
    def _utilization(nodes: list[OrchestrationNode]) -> float:
        if not nodes:
            return 0.0
        ratios = [
            max(
                node.cpu_used_millicores / node.cpu_capacity_millicores,
                node.memory_used_mb / node.memory_capacity_mb,
            )
            for node in nodes
        ]
        return sum(ratios) / len(ratios)

    @staticmethod
    def _utilization_from_usage(
        nodes: dict[str, OrchestrationNode], usage: dict[str, list[int]]
    ) -> float:
        if not nodes:
            return 0.0
        ratios = [
            max(
                cpu / nodes[node_id].cpu_capacity_millicores,
                memory / nodes[node_id].memory_capacity_mb,
            )
            for node_id, (cpu, memory) in sorted(usage.items())
        ]
        return sum(ratios) / len(ratios)


__all__ = ["EdgeResourceOrchestrator"]
