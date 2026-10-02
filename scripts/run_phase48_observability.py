from __future__ import annotations

import json

from sag_network.observability import (
    correlation_id,
    HealthStatus,
    MetricType,
    ObservabilityRecorder,
)


def main() -> None:
    recorder = ObservabilityRecorder()
    correlation = correlation_id(component="sag-observer", operation="phase48-demo", sequence=48)
    recorder.record_metric(
        name="telemetry_records",
        metric_type=MetricType.COUNTER,
        value=48,
        timestamp_s=48.0,
        labels={"domain": "unified"},
        correlation=correlation,
    )
    recorder.record_metric(
        name="wireless_latency_ms",
        metric_type=MetricType.GAUGE,
        value=4.25,
        timestamp_s=48.0,
        labels={"transport": "synthetic"},
        correlation=correlation,
    )
    recorder.record_event(
        timestamp_s=48.0,
        component="sag-observer",
        event_name="observation_snapshot_created",
        correlation=correlation,
        attributes={"phase": "48", "source": "offline-fixture"},
    )
    recorder.update_health(
        component="edge-runtime",
        status=HealthStatus.HEALTHY,
        checks_total=10,
        checks_failed=0,
        timestamp_s=48.0,
    )
    recorder.update_health(
        component="wireless-transport",
        status=HealthStatus.DEGRADED,
        checks_total=10,
        checks_failed=1,
        timestamp_s=48.0,
    )
    snapshot = recorder.snapshot(
        timestamp_s=48.0, fixture="synthetic offline observability fixture"
    )
    print(
        json.dumps(
            {
                "name": "Observability",
                "phase": "48",
                "status": "pass",
                "metric_count": snapshot.metric_count,
                "event_count": snapshot.event_count,
                "healthy_components": snapshot.healthy_components,
                "degraded_components": snapshot.degraded_components,
                "unhealthy_components": snapshot.unhealthy_components,
                "correlation_id": correlation,
                "snapshot_fingerprint": snapshot.snapshot_fingerprint,
                "external_exporter_used": False,
                "network_mutation": False,
                "fixture": snapshot.fixture,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
