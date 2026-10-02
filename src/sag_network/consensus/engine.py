from __future__ import annotations

import hashlib
import json

from sag_network.consensus.models import (
    ConsensusConfig,
    ConsensusResult,
    ConsensusSnapshot,
    ReplicaStatus,
    StateUpdate,
    StateVersion,
)


class DistributedStateConsensus:
    """Deterministic quorum state store for an offline distributed-systems model."""

    def __init__(self, config: ConsensusConfig) -> None:
        self.config = config
        self._sequence = 0
        self._state: dict[str, StateUpdate] = {}

    @property
    def quorum(self) -> int:
        return len(self.config.replicas) // 2 + 1

    @property
    def available_replicas(self) -> int:
        return sum(item.status is ReplicaStatus.AVAILABLE for item in self.config.replicas)

    def propose(self, *, key: str, value: str, writer_id: str) -> ConsensusResult:
        self._sequence += 1
        version = StateVersion(
            epoch=self.config.epoch,
            sequence=self._sequence,
            writer_id=writer_id,
        )
        acknowledgements = self.available_replicas
        current = self._state.get(key)
        if acknowledgements < self.quorum:
            committed = False
            reason = "quorum unavailable; update not committed"
        elif current is not None and version.ordering_key() <= current.version.ordering_key():
            committed = False
            reason = "stale version rejected"
        else:
            self._state[key] = StateUpdate(key=key, value=value, version=version)
            committed = True
            reason = "quorum committed update"
        return ConsensusResult(
            key=key,
            committed=committed,
            reason=reason,
            acknowledgements=acknowledgements,
            quorum=self.quorum,
            version=version,
            value=value if committed else (current.value if current is not None else value),
            state_fingerprint=self._fingerprint(),
        )

    def merge(self, update: StateUpdate) -> bool:
        current = self._state.get(update.key)
        if current is not None and update.version.ordering_key() <= current.version.ordering_key():
            return False
        self._state[update.key] = update
        return True

    def get(self, key: str) -> StateUpdate | None:
        return self._state.get(key)

    def snapshot(self) -> ConsensusSnapshot:
        return ConsensusSnapshot(
            cluster_id=self.config.cluster_id,
            epoch=self.config.epoch,
            available_replicas=self.available_replicas,
            total_replicas=len(self.config.replicas),
            quorum=self.quorum,
            committed_keys=len(self._state),
            deterministic_fingerprint=self._fingerprint(),
        )

    def _fingerprint(self) -> str:
        payload = {
            "cluster_id": self.config.cluster_id,
            "epoch": self.config.epoch,
            "state": {
                key: update.model_dump(mode="json")
                for key, update in sorted(self._state.items())
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["DistributedStateConsensus"]
