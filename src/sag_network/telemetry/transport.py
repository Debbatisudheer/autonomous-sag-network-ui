from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import RLock

from pydantic import BaseModel, Field

from sag_network.telemetry.models import (
    TelemetryIngestResult,
    TelemetryRecord,
)
from sag_network.telemetry.state import TelemetryStateStore


class TelemetryTransportError(RuntimeError):
    """Raised when the real-time telemetry transport cannot accept an operation."""


class TelemetryTransportConfig(BaseModel):
    """Deterministic limits for in-process real-time telemetry transport."""

    max_pending_records: int = Field(default=1024, ge=1)
    retain_delivered_records: int = Field(default=1000, ge=0)


class TelemetryEnvelope(BaseModel):
    """Transport envelope preserving a normalized telemetry record and routing metadata."""

    transport_sequence: int = Field(ge=0)
    topic: str = Field(min_length=1)
    record: TelemetryRecord


class TelemetryPublishResult(BaseModel):
    """Deterministic result of publishing one telemetry record."""

    accepted: bool
    transport_sequence: int | None = None
    subscriber_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    reason: str | None = None


class TelemetryTransportStats(BaseModel):
    """Transport counters suitable for operational validation and observability."""

    published: int = Field(ge=0)
    delivered: int = Field(ge=0)
    rejected: int = Field(ge=0)
    pending: int = Field(ge=0)
    subscribers: int = Field(ge=0)


@dataclass(frozen=True)
class _Subscriber:
    subscriber_id: str
    callback: Callable[[TelemetryEnvelope], None]


class InMemoryTelemetryTransport:
    """Thread-safe deterministic push transport for real-time telemetry.

    This is deliberately an in-process transport for Phase 30. It establishes the
    transport contract without introducing an external broker dependency. Delivery
    order follows publication order and subscriber registration order.
    """

    def __init__(self, config: TelemetryTransportConfig | None = None) -> None:
        self.config = config or TelemetryTransportConfig()
        self._lock = RLock()
        self._next_sequence = 0
        self._pending: deque[TelemetryEnvelope] = deque(
            maxlen=self.config.max_pending_records
        )
        self._delivered: deque[TelemetryEnvelope] = deque(
            maxlen=self.config.retain_delivered_records
        )
        self._subscribers: list[_Subscriber] = []
        self._published = 0
        self._delivered_count = 0
        self._rejected = 0

    @staticmethod
    def topic_for(record: TelemetryRecord) -> str:
        """Build a stable topic from domain and metric without altering the record."""
        return f"telemetry.{record.domain.value}.{record.metric.value}"

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def delivered_history(self) -> tuple[TelemetryEnvelope, ...]:
        with self._lock:
            return tuple(self._delivered)

    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[TelemetryEnvelope], None],
    ) -> None:
        """Register one ordered subscriber."""
        if not subscriber_id:
            raise ValueError("subscriber_id must not be empty")
        with self._lock:
            if any(item.subscriber_id == subscriber_id for item in self._subscribers):
                raise ValueError(f"subscriber already exists: {subscriber_id}")
            self._subscribers.append(_Subscriber(subscriber_id, callback))

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscriber and report whether it existed."""
        with self._lock:
            for index, subscriber in enumerate(self._subscribers):
                if subscriber.subscriber_id == subscriber_id:
                    del self._subscribers[index]
                    return True
        return False

    def publish(self, record: TelemetryRecord) -> TelemetryPublishResult:
        """Publish one record and synchronously deliver it to all subscribers."""
        with self._lock:
            if len(self._pending) >= self.config.max_pending_records:
                self._rejected += 1
                return TelemetryPublishResult(
                    accepted=False,
                    subscriber_count=len(self._subscribers),
                    pending_count=len(self._pending),
                    reason="transport pending queue is full",
                )
            envelope = TelemetryEnvelope(
                transport_sequence=self._next_sequence,
                topic=self.topic_for(record),
                record=record,
            )
            self._next_sequence += 1
            self._pending.append(envelope)
            self._published += 1
            subscribers = tuple(self._subscribers)

        delivered = 0
        for subscriber in subscribers:
            try:
                subscriber.callback(envelope)
            except Exception:
                with self._lock:
                    self._rejected += 1
                    self._pending.remove(envelope)
                raise
            delivered += 1

        with self._lock:
            if envelope in self._pending:
                self._pending.remove(envelope)
            self._delivered.append(envelope)
            self._delivered_count += delivered
            return TelemetryPublishResult(
                accepted=True,
                transport_sequence=envelope.transport_sequence,
                subscriber_count=delivered,
                pending_count=len(self._pending),
            )

    def publish_many(self, records: Iterable[TelemetryRecord]) -> tuple[TelemetryPublishResult, ...]:
        """Publish records in input order."""
        return tuple(self.publish(record) for record in records)

    def stats(self) -> TelemetryTransportStats:
        """Return a point-in-time deterministic counter snapshot."""
        with self._lock:
            return TelemetryTransportStats(
                published=self._published,
                delivered=self._delivered_count,
                rejected=self._rejected,
                pending=len(self._pending),
                subscribers=len(self._subscribers),
            )


class TelemetryStateTransportConsumer:
    """Bridge real-time transport envelopes into the existing state store."""

    def __init__(self, state_store: TelemetryStateStore) -> None:
        self.state_store = state_store
        self.results: list[TelemetryIngestResult] = []

    def consume(self, envelope: TelemetryEnvelope) -> TelemetryIngestResult:
        """Ingest a transported record using its own simulation timestamp as reference."""
        result = self.state_store.ingest(
            envelope.record,
            reference_time_s=envelope.record.timestamp_s,
        )
        self.results.append(result)
        return result
