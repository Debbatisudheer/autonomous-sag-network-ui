from __future__ import annotations

import hashlib
import json

from sag_network.deployment.models import (
    DeploymentStatus,
    EdgeDeploymentReport,
    EdgeRuntimeConfig,
    EdgeWorkload,
    RuntimeHealth,
    RuntimeHealthReport,
    WorkloadAdmission,
)


class EdgeDeploymentRuntime:
    """Resource-aware local edge runtime and offline deployment harness."""

    def __init__(self, config: EdgeRuntimeConfig) -> None:
        self.config = config
        self._workloads: dict[str, EdgeWorkload] = {}
        self._last_heartbeat_s: float | None = None

    @property
    def active_workloads(self) -> tuple[EdgeWorkload, ...]:
        return tuple(self._workloads[key] for key in sorted(self._workloads))

    def _used_cpu(self) -> int:
        return sum(item.cpu_millicores for item in self._workloads.values())

    def _used_memory(self) -> int:
        return sum(item.memory_mb for item in self._workloads.values())

    def admit(self, workload: EdgeWorkload) -> WorkloadAdmission:
        if workload.workload_id in self._workloads:
            return WorkloadAdmission(
                workload_id=workload.workload_id,
                admitted=False,
                reason="workload_id already admitted",
                cpu_headroom_millicores=max(0, self.config.cpu_limit_millicores - self._used_cpu()),
                memory_headroom_mb=max(0, self.config.memory_limit_mb - self._used_memory()),
            )
        cpu_headroom = max(0, self.config.cpu_limit_millicores - self._used_cpu())
        memory_headroom = max(0, self.config.memory_limit_mb - self._used_memory())
        if len(self._workloads) >= self.config.maximum_concurrent_tasks:
            reason = "maximum concurrent workload limit reached"
            admitted = False
        elif workload.cpu_millicores > cpu_headroom:
            reason = "insufficient CPU headroom"
            admitted = False
        elif workload.memory_mb > memory_headroom:
            reason = "insufficient memory headroom"
            admitted = False
        else:
            self._workloads[workload.workload_id] = workload
            admitted = True
            reason = "workload admitted within deterministic resource limits"
        return WorkloadAdmission(
            workload_id=workload.workload_id,
            admitted=admitted,
            reason=reason,
            cpu_headroom_millicores=cpu_headroom,
            memory_headroom_mb=memory_headroom,
        )

    def heartbeat(self, timestamp_s: float) -> None:
        if self._last_heartbeat_s is not None and timestamp_s <= self._last_heartbeat_s:
            raise ValueError("heartbeat timestamps must increase strictly")
        self._last_heartbeat_s = timestamp_s

    def health(self, timestamp_s: float) -> RuntimeHealthReport:
        cpu_ratio = self._used_cpu() / self.config.cpu_limit_millicores
        memory_ratio = self._used_memory() / self.config.memory_limit_mb
        live = (
            self._last_heartbeat_s is not None
            and timestamp_s - self._last_heartbeat_s <= self.config.health_timeout_s
        )
        if not live:
            status = RuntimeHealth.OFFLINE
        elif (
            cpu_ratio >= self.config.degraded_cpu_ratio
            or memory_ratio >= self.config.degraded_memory_ratio
        ):
            status = RuntimeHealth.DEGRADED
        else:
            status = RuntimeHealth.HEALTHY
        readiness = live and status is not RuntimeHealth.OFFLINE
        fingerprint = self._fingerprint(
            {
                "runtime_id": self.config.runtime_id,
                "timestamp_s": timestamp_s,
                "cpu_ratio": cpu_ratio,
                "memory_ratio": memory_ratio,
                "active_workloads": sorted(self._workloads),
                "status": status.value,
            }
        )
        return RuntimeHealthReport(
            runtime_id=self.config.runtime_id,
            timestamp_s=timestamp_s,
            status=status,
            cpu_utilization_ratio=cpu_ratio,
            memory_utilization_ratio=memory_ratio,
            active_workloads=len(self._workloads),
            liveness=live,
            readiness=readiness,
            deterministic_fingerprint=fingerprint,
        )

    def deploy_offline(
        self, *, timestamp_s: float, workloads: list[EdgeWorkload]
    ) -> EdgeDeploymentReport:
        ordered_workloads = sorted(
            workloads, key=lambda item: (-item.priority, item.workload_id)
        )
        admissions = [self.admit(item) for item in ordered_workloads]
        self.heartbeat(timestamp_s)
        health = self.health(timestamp_s)
        rejected_count = sum(not item.admitted for item in admissions)
        status = DeploymentStatus.READY if rejected_count == 0 else DeploymentStatus.DEGRADED
        deployment_fingerprint = self._fingerprint(
            {
                "runtime_id": self.config.runtime_id,
                "timestamp_s": timestamp_s,
                "admissions": [item.model_dump(mode="json") for item in admissions],
                "health": health.model_dump(mode="json"),
            }
        )
        return EdgeDeploymentReport(
            runtime_id=self.config.runtime_id,
            timestamp_s=timestamp_s,
            status=status,
            admissions=admissions,
            health=health,
            admitted_count=len(admissions) - rejected_count,
            rejected_count=rejected_count,
            deployment_fingerprint=deployment_fingerprint,
        )

    @staticmethod
    def _fingerprint(payload: object) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["EdgeDeploymentRuntime"]
