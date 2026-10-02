from __future__ import annotations

import json

from sag_network.deployment import EdgeDeploymentRuntime, EdgeRuntimeConfig, EdgeWorkload


def main() -> None:
    runtime = EdgeDeploymentRuntime(
        EdgeRuntimeConfig(
            runtime_id="edge-runtime-a",
            cpu_limit_millicores=1000,
            memory_limit_mb=1024,
            maximum_concurrent_tasks=3,
        )
    )
    report = runtime.deploy_offline(
        timestamp_s=40.0,
        workloads=[
            EdgeWorkload(
                workload_id="prediction",
                cpu_millicores=250,
                memory_mb=256,
                latency_budget_ms=20.0,
                priority=90,
            ),
            EdgeWorkload(
                workload_id="decision",
                cpu_millicores=300,
                memory_mb=256,
                latency_budget_ms=20.0,
                priority=80,
            ),
            EdgeWorkload(
                workload_id="digital-twin",
                cpu_millicores=250,
                memory_mb=256,
                latency_budget_ms=50.0,
                priority=70,
            ),
            EdgeWorkload(
                workload_id="overflow",
                cpu_millicores=200,
                memory_mb=128,
                latency_budget_ms=50.0,
                priority=10,
            ),
        ],
    )
    print(
        json.dumps(
            {
                "name": "Real Edge Deployment",
                "phase": "40",
                "status": "pass" if report.health.readiness else "fail",
                "runtime_id": report.runtime_id,
                "admitted_count": report.admitted_count,
                "rejected_count": report.rejected_count,
                "health": report.health.status.value,
                "liveness": report.health.liveness,
                "readiness": report.health.readiness,
                "cpu_utilization_ratio": report.health.cpu_utilization_ratio,
                "memory_utilization_ratio": report.health.memory_utilization_ratio,
                "deployment_fingerprint": report.deployment_fingerprint,
                "external_process_started": report.external_process_started,
                "fixture": "synthetic offline edge deployment fixture",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
