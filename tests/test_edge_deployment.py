from sag_network.deployment import (
    EdgeDeploymentRuntime,
    EdgeRuntimeConfig,
    EdgeWorkload,
    RuntimeHealth,
)


def workload(
    workload_id: str, cpu: int = 200, memory: int = 128, priority: int = 0
) -> EdgeWorkload:
    return EdgeWorkload(
        workload_id=workload_id,
        cpu_millicores=cpu,
        memory_mb=memory,
        latency_budget_ms=50.0,
        priority=priority,
    )


def test_resource_admission_is_deterministic() -> None:
    runtime = EdgeDeploymentRuntime(
        EdgeRuntimeConfig(runtime_id="edge-a", cpu_limit_millicores=500, memory_limit_mb=512)
    )
    first = runtime.admit(workload("a", cpu=300, memory=256))
    second = runtime.admit(workload("b", cpu=250, memory=256))
    assert first.admitted
    assert not second.admitted
    assert second.reason == "insufficient CPU headroom"


def test_duplicate_workload_is_rejected() -> None:
    runtime = EdgeDeploymentRuntime(EdgeRuntimeConfig(runtime_id="edge-a"))
    assert runtime.admit(workload("a")).admitted
    duplicate = runtime.admit(workload("a"))
    assert not duplicate.admitted
    assert duplicate.reason == "workload_id already admitted"


def test_health_requires_recent_heartbeat() -> None:
    runtime = EdgeDeploymentRuntime(EdgeRuntimeConfig(runtime_id="edge-a", health_timeout_s=2.0))
    offline = runtime.health(1.0)
    assert offline.status is RuntimeHealth.OFFLINE
    runtime.heartbeat(1.0)
    healthy = runtime.health(2.0)
    assert healthy.status is RuntimeHealth.HEALTHY
    assert healthy.liveness
    assert healthy.readiness


def test_offline_deployment_harness_is_resource_aware() -> None:
    runtime = EdgeDeploymentRuntime(
        EdgeRuntimeConfig(
            runtime_id="edge-a", cpu_limit_millicores=1000, maximum_concurrent_tasks=2
        )
    )
    report = runtime.deploy_offline(
        timestamp_s=40.0,
        workloads=[
            workload("low", cpu=200, priority=1),
            workload("high", cpu=500, priority=9),
            workload("overflow", cpu=200, priority=0),
        ],
    )
    assert report.admitted_count == 2
    assert report.rejected_count == 1
    assert report.health.status is RuntimeHealth.HEALTHY
    assert report.external_process_started is False
