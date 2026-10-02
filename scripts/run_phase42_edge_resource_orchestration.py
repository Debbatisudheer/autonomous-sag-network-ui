from __future__ import annotations

import json

from sag_network.orchestration import (
    EdgeResourceOrchestrator,
    OrchestrationNode,
    OrchestrationWorkload,
)


def main() -> None:
    report = EdgeResourceOrchestrator().plan(
        timestamp_s=42.0,
        nodes=[
            OrchestrationNode(
                node_id="edge-a", cpu_capacity_millicores=1000, memory_capacity_mb=1000
            ),
            OrchestrationNode(
                node_id="edge-b", cpu_capacity_millicores=1000, memory_capacity_mb=1000
            ),
            OrchestrationNode(
                node_id="edge-c",
                cpu_capacity_millicores=1000,
                memory_capacity_mb=1000,
                cpu_used_millicores=850,
                memory_used_mb=850,
                healthy=True,
            ),
        ],
        workloads=[
            OrchestrationWorkload(
                workload_id="prediction", cpu_millicores=300, memory_mb=300, priority=90
            ),
            OrchestrationWorkload(
                workload_id="decision", cpu_millicores=250, memory_mb=250, priority=80
            ),
            OrchestrationWorkload(
                workload_id="twin",
                cpu_millicores=250,
                memory_mb=250,
                priority=70,
                anti_affinity_group="control",
            ),
            OrchestrationWorkload(
                workload_id="recovery",
                cpu_millicores=300,
                memory_mb=300,
                priority=60,
                anti_affinity_group="control",
            ),
        ],
        assignments={"twin": "edge-c", "recovery": "edge-c"},
    )
    print(json.dumps({
        "name": "Edge Resource Orchestration",
        "phase": "42",
        "status": "pass",
        "placement_count": len(report.placements),
        "rejected_count": len(report.rejected_workload_ids),
        "moved_count": len(report.moved_workload_ids),
        "rebalance_required": report.rebalance_required,
        "utilization_before": report.utilization_before,
        "utilization_after": report.utilization_after,
        "plan_fingerprint": report.plan_fingerprint,
        "external_process_started": False,
        "fixture": "synthetic offline edge orchestration fixture",
        "network_mutation": False,
    }, indent=2))


if __name__ == "__main__":
    main()
