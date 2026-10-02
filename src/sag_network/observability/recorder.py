from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from sag_network.observability.models import (
    ComponentHealth,
    HealthStatus,
    MetricSample,
    MetricType,
    ObservabilitySnapshot,
    TraceEvent,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def correlation_id(*, component: str, operation: str, sequence: int) -> str:
    """Build a stable correlation identifier for one deterministic operation."""
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    payload = {"component": component, "operation": operation, "sequence": sequence}
    return _fingerprint(payload)[:24]


class ObservabilityRecorder:
    """In-memory metrics, event, and health recorder with deterministic exports."""

    def __init__(self) -> None:
        self._metrics: list[MetricSample] = []
        self._events: list[TraceEvent] = []
        self._health: dict[str, ComponentHealth] = {}

    def record_metric(
        self,
        *,
        name: str,
        metric_type: MetricType,
        value: float,
        timestamp_s: float,
        labels: Mapping[str, str] | None = None,
        correlation: str,
    ) -> MetricSample:
        sample = MetricSample(
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp_s=timestamp_s,
            labels=dict(labels or {}),
            correlation_id=correlation,
        )
        if metric_type is MetricType.COUNTER and value < 0:
            raise ValueError("counter values cannot be negative")
        self._metrics.append(sample)
        return sample

    def record_event(
        self,
        *,
        timestamp_s: float,
        component: str,
        event_name: str,
        correlation: str,
        attributes: Mapping[str, str] | None = None,
    ) -> TraceEvent:
        normalized_attributes = dict(attributes or {})
        event = TraceEvent(
            event_id=_fingerprint(
                {
                    "timestamp_s": timestamp_s,
                    "component": component,
                    "event_name": event_name,
                    "correlation_id": correlation,
                    "attributes": normalized_attributes,
                }
            )[:24],
            timestamp_s=timestamp_s,
            component=component,
            event_name=event_name,
            correlation_id=correlation,
            attributes=normalized_attributes,
        )
        self._events.append(event)
        return event

    def update_health(
        self,
        *,
        component: str,
        status: HealthStatus,
        checks_total: int,
        checks_failed: int,
        timestamp_s: float | None,
    ) -> ComponentHealth:
        if checks_failed > checks_total:
            raise ValueError("failed checks cannot exceed total checks")
        health = ComponentHealth(
            component=component,
            status=status,
            checks_total=checks_total,
            checks_failed=checks_failed,
            last_check_timestamp_s=timestamp_s,
        )
        self._health[component] = health
        return health

    def snapshot(self, *, timestamp_s: float, fixture: str) -> ObservabilitySnapshot:
        metrics = tuple(
            sorted(
                self._metrics,
                key=lambda item: (
                    item.timestamp_s,
                    item.name,
                    item.correlation_id,
                    item.metric_type.value,
                ),
            )
        )
        events = tuple(
            sorted(
                self._events,
                key=lambda item: (item.timestamp_s, item.component, item.event_id),
            )
        )
        health = tuple(sorted(self._health.values(), key=lambda item: item.component))
        health_counts = {
            status: sum(item.status is status for item in health) for status in HealthStatus
        }
        payload = {
            "timestamp_s": timestamp_s,
            "metrics": [item.model_dump(mode="json") for item in metrics],
            "events": [item.model_dump(mode="json") for item in events],
            "health": [item.model_dump(mode="json") for item in health],
        }
        return ObservabilitySnapshot(
            timestamp_s=timestamp_s,
            metrics=metrics,
            events=events,
            health=health,
            metric_count=len(metrics),
            event_count=len(events),
            healthy_components=health_counts[HealthStatus.HEALTHY],
            degraded_components=health_counts[HealthStatus.DEGRADED],
            unhealthy_components=health_counts[HealthStatus.UNHEALTHY],
            snapshot_fingerprint=_fingerprint(payload),
            fixture=fixture,
        )

    def export_records(
        self,
    ) -> Sequence[MetricSample | TraceEvent | ComponentHealth]:
        """Return immutable ordered records for external exporters."""
        return (*self._metrics, *self._events, *self._health.values())
