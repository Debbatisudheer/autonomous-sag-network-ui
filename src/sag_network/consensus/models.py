from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ReplicaStatus(str, Enum):
    AVAILABLE = "available"
    PARTITIONED = "partitioned"


class StateVersion(BaseModel):
    """Monotonic logical version for one replicated state key."""

    epoch: int = Field(ge=0)
    sequence: int = Field(ge=0)
    writer_id: str = Field(min_length=1)

    def ordering_key(self) -> tuple[int, int, str]:
        return self.epoch, self.sequence, self.writer_id


class StateUpdate(BaseModel):
    key: str = Field(min_length=1)
    value: str
    version: StateVersion


class Replica(BaseModel):
    replica_id: str = Field(min_length=1)
    status: ReplicaStatus = ReplicaStatus.AVAILABLE


class ConsensusConfig(BaseModel):
    cluster_id: str = Field(min_length=1)
    replicas: list[Replica] = Field(min_length=1)
    epoch: int = Field(default=0, ge=0)


class ConsensusResult(BaseModel):
    key: str = Field(min_length=1)
    committed: bool
    reason: str = Field(min_length=1)
    acknowledgements: int = Field(ge=0)
    quorum: int = Field(ge=1)
    version: StateVersion
    value: str
    state_fingerprint: str = Field(min_length=64, max_length=64)


class ConsensusSnapshot(BaseModel):
    cluster_id: str = Field(min_length=1)
    epoch: int = Field(ge=0)
    available_replicas: int = Field(ge=0)
    total_replicas: int = Field(ge=1)
    quorum: int = Field(ge=1)
    committed_keys: int = Field(ge=0)
    deterministic_fingerprint: str = Field(min_length=64, max_length=64)


__all__ = [
    "ConsensusConfig",
    "ConsensusResult",
    "ConsensusSnapshot",
    "Replica",
    "ReplicaStatus",
    "StateUpdate",
    "StateVersion",
]
