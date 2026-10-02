from __future__ import annotations

import hashlib
import json
from collections import deque

from pydantic import BaseModel, Field

from sag_network.decision.models import DecisionPriority


class DistributedMessage(BaseModel):
    """Deterministic message envelope for logical distributed communication."""

    message_id: str = Field(min_length=16)
    source_node_id: str = Field(min_length=1)
    destination_node_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    priority: DecisionPriority
    payload_hash: str = Field(min_length=64, max_length=64)
    ttl_s: float = Field(default=5.0, gt=0)
    delivered: bool = False


class InMemoryMessageBroker:
    """Bounded deterministic message broker used by the distributed testbed."""

    def __init__(self, history_limit: int = 1000) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be positive")
        self._queues: dict[str, deque[DistributedMessage]] = {}
        self._history: deque[DistributedMessage] = deque(maxlen=history_limit)

    @staticmethod
    def create_message(
        *,
        source_node_id: str,
        destination_node_id: str,
        topic: str,
        timestamp_s: float,
        priority: DecisionPriority,
        payload: dict[str, object],
        ttl_s: float = 5.0,
    ) -> DistributedMessage:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        message_id = hashlib.sha256(
            f"{source_node_id}|{destination_node_id}|{topic}|{timestamp_s}|{payload_hash}".encode()
        ).hexdigest()[:16]
        return DistributedMessage(
            message_id=message_id,
            source_node_id=source_node_id,
            destination_node_id=destination_node_id,
            topic=topic,
            timestamp_s=timestamp_s,
            priority=priority,
            payload_hash=payload_hash,
            ttl_s=ttl_s,
        )

    def publish(self, message: DistributedMessage) -> None:
        queue = self._queues.setdefault(message.destination_node_id, deque())
        queue.append(message)
        self._history.append(message)

    def consume(self, node_id: str, *, now_s: float) -> list[DistributedMessage]:
        queue = self._queues.setdefault(node_id, deque())
        delivered: list[DistributedMessage] = []
        while queue:
            message = queue.popleft()
            if now_s - message.timestamp_s > message.ttl_s:
                continue
            delivered.append(message.model_copy(update={"delivered": True}))
        delivered.sort(
            key=lambda item: (-_priority_rank(item.priority.value), item.message_id)
        )
        return delivered

    @property
    def history(self) -> list[DistributedMessage]:
        return list(self._history)


__all__ = ["DistributedMessage", "InMemoryMessageBroker"]


def _priority_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(value, -1)
