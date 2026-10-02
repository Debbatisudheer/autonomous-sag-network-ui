from sag_network.orchestration import (
    EdgeResourceOrchestrator,
    OrchestrationDecision,
    OrchestrationNode,
    OrchestrationWorkload,
)


def nodes() -> list[OrchestrationNode]:
    return [
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
            healthy=False,
        ),
    ]


def test_priority_and_capacity_are_deterministic() -> None:
    report = EdgeResourceOrchestrator().plan(
        timestamp_s=1.0,
        nodes=nodes(),
        workloads=[
            OrchestrationWorkload(
                workload_id="low", cpu_millicores=500, memory_mb=200, priority=10
            ),
            OrchestrationWorkload(
                workload_id="high", cpu_millicores=500, memory_mb=200, priority=90
            ),
        ],
    )
    assert [item.node_id for item in report.placements] == ["edge-a", "edge-b"]
    assert all(
        item.decision is OrchestrationDecision.PLACE for item in report.placements
    )


def test_unhealthy_node_is_not_selected() -> None:
    report = EdgeResourceOrchestrator().plan(
        timestamp_s=1.0,
        nodes=nodes(),
        workloads=[
            OrchestrationWorkload(
                workload_id="w", cpu_millicores=100, memory_mb=100, priority=1
            )
        ],
    )
    assert report.placements[0].node_id == "edge-a"


def test_anti_affinity_rebalances_to_second_node() -> None:
    report = EdgeResourceOrchestrator().plan(
        timestamp_s=1.0,
        nodes=nodes(),
        workloads=[
            OrchestrationWorkload(
                workload_id="a",
                cpu_millicores=300,
                memory_mb=300,
                priority=10,
                anti_affinity_group="g",
            ),
            OrchestrationWorkload(
                workload_id="b",
                cpu_millicores=300,
                memory_mb=300,
                priority=10,
                anti_affinity_group="g",
            ),
        ],
    )
    assert [item.node_id for item in report.placements] == ["edge-a", "edge-b"]


def test_existing_assignment_is_kept_when_feasible() -> None:
    report = EdgeResourceOrchestrator().plan(
        timestamp_s=1.0,
        nodes=nodes(),
        workloads=[
            OrchestrationWorkload(
                workload_id="w", cpu_millicores=100, memory_mb=100, priority=10
            )
        ],
        assignments={"w": "edge-b"},
    )
    assert report.placements[0].decision is OrchestrationDecision.KEEP
    assert report.placements[0].node_id == "edge-b"
    assert report.moved_workload_ids == []


def test_infeasible_workload_is_rejected() -> None:
    second = EdgeResourceOrchestrator().plan(
        timestamp_s=1.0,
        nodes=nodes(),
        workloads=[
            OrchestrationWorkload(
                workload_id="a", cpu_millicores=800, memory_mb=800, priority=3
            ),
            OrchestrationWorkload(
                workload_id="b", cpu_millicores=800, memory_mb=800, priority=2
            ),
            OrchestrationWorkload(
                workload_id="c", cpu_millicores=300, memory_mb=300, priority=1
            ),
        ],
    )
    assert second.rejected_workload_ids == ["c"]


def test_rebalance_is_reported() -> None:
    report = EdgeResourceOrchestrator().plan(
        timestamp_s=1.0,
        nodes=nodes(),
        workloads=[
            OrchestrationWorkload(
                workload_id="w", cpu_millicores=300, memory_mb=300, priority=10
            )
        ],
        assignments={"w": "edge-c"},
    )
    assert report.rebalance_required
    assert report.moved_workload_ids == ["w"]
    assert report.placements[0].decision is OrchestrationDecision.REBALANCE


def test_fingerprint_is_deterministic() -> None:
    kwargs = {
        "timestamp_s": 2.0,
        "nodes": nodes(),
        "workloads": [
            OrchestrationWorkload(
                workload_id="w",
                cpu_millicores=100,
                memory_mb=100,
                priority=1,
            )
        ],
    }
    first = EdgeResourceOrchestrator().plan(**kwargs)
    second = EdgeResourceOrchestrator().plan(**kwargs)
    assert first.plan_fingerprint == second.plan_fingerprint
