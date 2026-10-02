from __future__ import annotations

from collections import deque

from sag_network.edge.models import DistributedStateConfig, StateReplica


class DistributedStateStore:
    """In-memory versioned state store with deterministic replica convergence."""

    def __init__(self, config: DistributedStateConfig | None = None) -> None:
        self.config = config or DistributedStateConfig()
        self._latest: dict[tuple[str, str], StateReplica] = {}
        self._history: deque[StateReplica] = deque(maxlen=self.config.history_limit)

    def upsert(self, replica: StateReplica) -> bool:
        key = (replica.state_key, replica.source_node_id)
        current = self._latest.get(key)
        if current is not None:
            if self.config.enforce_monotonic_version and replica.version < current.version:
                return False
            if (
                self.config.enforce_monotonic_timestamp
                and replica.timestamp_s < current.timestamp_s
            ):
                return False
            if replica.version == current.version and replica.state_hash == current.state_hash:
                return False
        self._latest[key] = replica
        self._history.append(replica)
        return True

    def get(self, state_key: str, source_node_id: str | None = None) -> StateReplica | None:
        if source_node_id is not None:
            return self._latest.get((state_key, source_node_id))
        replicas = [
            replica
            for (key, _), replica in self._latest.items()
            if key == state_key
        ]
        return max(replicas, key=lambda item: (item.version, item.timestamp_s, item.source_node_id), default=None)

    def replicas(self, state_key: str) -> list[StateReplica]:
        return sorted(
            [
                replica
                for (key, _), replica in self._latest.items()
                if key == state_key
            ],
            key=lambda item: item.source_node_id,
        )

    def is_converged(self, state_key: str) -> bool:
        replicas = self.replicas(state_key)
        if not replicas:
            return False
        return len({replica.state_hash for replica in replicas}) == 1

    @property
    def history(self) -> list[StateReplica]:
        return list(self._history)


__all__ = ["DistributedStateStore"]
