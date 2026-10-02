from __future__ import annotations

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry import (
    InMemoryTelemetryTransport,
    TelemetryMetric,
    TelemetryRecord,
    TelemetryStateStore,
    TelemetryStateTransportConsumer,
    TelemetryTransportConfig,
)


def record(sequence: int = 0, value: float = -80.0) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=f"r-{sequence}",
        timestamp_s=10.0 + sequence,
        sequence=sequence,
        source_id="sat-1",
        domain=NetworkDomain.SPACE,
        metric=TelemetryMetric.RECEIVED_POWER_DBM,
        value=value,
        unit="dBm",
    )


def test_topic_is_stable() -> None:
    transport = InMemoryTelemetryTransport()
    assert transport.topic_for(record()) == "telemetry.space.received_power_dbm"


def test_publish_delivers_in_registration_order() -> None:
    transport = InMemoryTelemetryTransport()
    received: list[tuple[str, int]] = []
    transport.subscribe("first", lambda envelope: received.append(("first", envelope.transport_sequence)))
    transport.subscribe("second", lambda envelope: received.append(("second", envelope.transport_sequence)))

    result = transport.publish(record())

    assert result.accepted is True
    assert result.transport_sequence == 0
    assert result.subscriber_count == 2
    assert received == [("first", 0), ("second", 0)]


def test_publish_sequence_is_monotonic() -> None:
    transport = InMemoryTelemetryTransport()
    first = transport.publish(record(0))
    second = transport.publish(record(1))

    assert first.transport_sequence == 0
    assert second.transport_sequence == 1
    assert [item.transport_sequence for item in transport.delivered_history] == [0, 1]


def test_duplicate_subscriber_is_rejected() -> None:
    transport = InMemoryTelemetryTransport()
    callback = lambda envelope: None
    transport.subscribe("consumer", callback)
    with pytest.raises(ValueError, match="subscriber already exists"):
        transport.subscribe("consumer", callback)


def test_unsubscribe_is_idempotent() -> None:
    transport = InMemoryTelemetryTransport()
    transport.subscribe("consumer", lambda envelope: None)
    assert transport.unsubscribe("consumer") is True
    assert transport.unsubscribe("consumer") is False


def test_callback_failure_does_not_mark_delivery_complete() -> None:
    transport = InMemoryTelemetryTransport()

    def fail(envelope: object) -> None:
        raise RuntimeError("consumer failed")

    transport.subscribe("failing", fail)
    with pytest.raises(RuntimeError, match="consumer failed"):
        transport.publish(record())
    assert transport.stats().delivered == 0
    assert transport.stats().rejected == 1


def test_state_consumer_preserves_existing_store_architecture() -> None:
    transport = InMemoryTelemetryTransport()
    store = TelemetryStateStore()
    consumer = TelemetryStateTransportConsumer(store)
    transport.subscribe("state-store", consumer.consume)

    result = transport.publish(record())

    assert result.accepted is True
    assert consumer.results[0].accepted_count == 1
    latest = store.latest_for(source_id="sat-1", metric=TelemetryMetric.RECEIVED_POWER_DBM.value)
    assert latest is not None
    assert latest.value == -80.0


def test_publish_many_preserves_input_order() -> None:
    transport = InMemoryTelemetryTransport()
    results = transport.publish_many([record(0), record(1), record(2)])
    assert [result.transport_sequence for result in results] == [0, 1, 2]


def test_stats_are_deterministic() -> None:
    transport = InMemoryTelemetryTransport()
    transport.subscribe("consumer", lambda envelope: None)
    transport.publish(record())
    assert transport.stats().model_dump() == {
        "published": 1,
        "delivered": 1,
        "rejected": 0,
        "pending": 0,
        "subscribers": 1,
    }


def test_config_rejects_invalid_pending_limit() -> None:
    with pytest.raises(ValueError):
        TelemetryTransportConfig(max_pending_records=0)
