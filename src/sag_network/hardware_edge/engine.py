from __future__ import annotations

import hashlib
import json
import os
import platform
import time
import tracemalloc
from collections.abc import Iterable

from sag_network.hardware_edge.models import (
    EdgeDeviceProfile,
    EdgeTelemetrySummary,
    EdgeWorkloadExecution,
    EdgeWorkloadSpec,
    HardwareEdgeDeploymentReport,
    HardwareEdgeEvidence,
)
from sag_network.telemetry.models import TelemetryRecord


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def synthetic_device_profile() -> EdgeDeviceProfile:
    return EdgeDeviceProfile(
        device_id="synthetic-edge-01",
        target_class="constrained-edge",
        operating_system="deterministic-fixture",
        architecture="portable",
        cpu_count=2,
        memory_limit_mb=256,
        storage_limit_mb=1024,
        observed_hardware=False,
    )


def local_host_profile(*, device_id: str = "local-host-edge") -> EdgeDeviceProfile:
    return EdgeDeviceProfile(
        device_id=device_id,
        target_class="local-host-edge",
        operating_system=platform.system() or "unknown",
        architecture=platform.machine() or "unknown",
        cpu_count=max(1, os.cpu_count() or 1),
        memory_limit_mb=4096,
        storage_limit_mb=16384,
        observed_hardware=True,
    )


class HardwareEdgeDeploymentEngine:
    """Execute a bounded telemetry workload inside an edge-style resource envelope."""

    def deploy(
        self,
        records: Iterable[TelemetryRecord],
        *,
        device: EdgeDeviceProfile,
        workload: EdgeWorkloadSpec,
        evidence_class: HardwareEdgeEvidence,
    ) -> HardwareEdgeDeploymentReport:
        record_list = list(records)
        if len(record_list) > workload.maximum_input_records:
            raise ValueError(
                "input record count exceeds the edge workload maximum_input_records"
            )

        values = [record.value for record in record_list]
        if not values:
            raise ValueError("at least one telemetry record is required")

        tracemalloc.start()
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        try:
            source_ids = sorted({record.source_id for record in record_list})
            mean_value = sum(values) / len(values)
            summary = EdgeTelemetrySummary(
                input_record_count=len(record_list),
                source_ids=source_ids,
                mean_value=mean_value,
                minimum_value=min(values),
                maximum_value=max(values),
                latest_timestamp_s=max(record.timestamp_s for record in record_list),
            )
            output_fingerprint = _fingerprint(summary.model_dump(mode="json"))
        finally:
            cpu_time_ms = (time.process_time_ns() - cpu_start) / 1_000_000.0
            wall_time_ms = (time.perf_counter_ns() - wall_start) / 1_000_000.0
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        peak_heap_kb = (peak_bytes + 1023) // 1024
        within_cpu = cpu_time_ms <= workload.max_cpu_time_ms
        within_wall = wall_time_ms <= workload.max_wall_time_ms
        within_heap = peak_heap_kb <= workload.max_python_heap_kb
        accepted = within_cpu and within_wall and within_heap
        reason = (
            "workload completed within configured edge resource budgets"
            if accepted
            else "workload exceeded one or more configured edge resource budgets"
        )
        execution = EdgeWorkloadExecution(
            workload_id=workload.workload_id,
            accepted=accepted,
            completed=True,
            input_record_count=len(record_list),
            cpu_time_ms=cpu_time_ms,
            wall_time_ms=wall_time_ms,
            peak_python_heap_kb=peak_heap_kb,
            within_cpu_budget=within_cpu,
            within_wall_budget=within_wall,
            within_heap_budget=within_heap,
            output_fingerprint=output_fingerprint,
            reason=reason,
        )
        deployment_payload = {
            "evidence_class": evidence_class.value,
            "device": device.model_dump(mode="json"),
            "workload_spec": workload.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
            "output_fingerprint": output_fingerprint,
        }
        return HardwareEdgeDeploymentReport(
            evidence_class=evidence_class,
            device=device,
            workload=execution,
            telemetry_summary=summary,
            deployment_fingerprint=_fingerprint(deployment_payload),
        )


__all__ = [
    "HardwareEdgeDeploymentEngine",
    "local_host_profile",
    "synthetic_device_profile",
]
