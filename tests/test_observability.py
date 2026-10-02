from __future__ import annotations

import pytest

from sag_network.observability import (
    correlation_id,
    HealthStatus,
    MetricType,
    ObservabilityRecorder,
)


def test_correlation_id_is_deterministic() -> None:
    assert correlation_id(component="edge", operation="admit", sequence=48) == correlation_id(
        component="edge", operation="admit", sequence=48
    )


def test_correlation_id_rejects_negative_sequence() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        correlation_id(component="edge", operation="admit", sequence=-1)


def test_counter_rejects_negative_value() -> None:
    recorder = ObservabilityRecorder()
    with pytest.raises(ValueError, match="negative"):
        recorder.record_metric(
            name="packets_sent",
            metric_type=MetricType.COUNTER,
            value=-1,
            timestamp_s=48.0,
            correlation="corr",
        )


def test_snapshot_counts_and_orders_records() -> None:
    recorder = ObservabilityRecorder()
    correlation = correlation_id(component="wireless", operation="exchange", sequence=1)
    recorder.record_metric(
        name="latency_ms",
        metric_type=MetricType.GAUGE,
        value=4.5,
        timestamp_s=2.0,
        correlation=correlation,
    )
    recorder.record_metric(
        name="packets_sent",
        metric_type=MetricType.COUNTER,
        value=2,
        timestamp_s=1.0,
        correlation=correlation,
    )
    recorder.record_event(
        timestamp_s=2.0,
        component="wireless",
        event_name="packet_delivered",
        correlation=correlation,
        attributes={"sequence": "48"},
    )
    recorder.update_health(
        component="wireless",
        status=HealthStatus.HEALTHY,
        checks_total=4,
        checks_failed=0,
        timestamp_s=2.0,
    )
    snapshot = recorder.snapshot(timestamp_s=48.0, fixture="test")
    assert snapshot.metric_count == 2
    assert snapshot.event_count == 1
    assert snapshot.healthy_components == 1
    assert snapshot.metrics[0].name == "packets_sent"
    assert len(snapshot.snapshot_fingerprint) == 64


def test_snapshot_is_deterministic() -> None:
    def build() -> str:
        recorder = ObservabilityRecorder()
        correlation = correlation_id(component="sdr", operation="decode", sequence=48)
        recorder.record_event(
            timestamp_s=3.0,
            component="sdr",
            event_name="frame_decoded",
            correlation=correlation,
        )
        recorder.update_health(
            component="sdr",
            status=HealthStatus.DEGRADED,
            checks_total=10,
            checks_failed=2,
            timestamp_s=3.0,
        )
        return recorder.snapshot(timestamp_s=48.0, fixture="test").snapshot_fingerprint

    assert build() == build()


def test_failed_checks_cannot_exceed_total() -> None:
    with pytest.raises(ValueError, match="exceed"):
        ObservabilityRecorder().update_health(
            component="sdr",
            status=HealthStatus.UNHEALTHY,
            checks_total=1,
            checks_failed=2,
            timestamp_s=1.0,
        )
