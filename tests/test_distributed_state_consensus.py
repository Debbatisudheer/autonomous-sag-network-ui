from sag_network.consensus import (
    ConsensusConfig,
    DistributedStateConsensus,
    Replica,
    ReplicaStatus,
    StateUpdate,
    StateVersion,
)


def config() -> ConsensusConfig:
    return ConsensusConfig(
        cluster_id="test",
        replicas=[
            Replica(replica_id="a"),
            Replica(replica_id="b"),
            Replica(replica_id="c"),
        ],
    )


def test_quorum_commit() -> None:
    store = DistributedStateConsensus(config())
    result = store.propose(key="route", value="uav-a", writer_id="a")
    assert result.committed
    assert result.acknowledgements == 3
    assert result.quorum == 2
    assert store.get("route").value == "uav-a"


def test_partition_without_quorum_does_not_commit() -> None:
    cfg = config().model_copy(update={"replicas": [
        Replica(replica_id="a", status=ReplicaStatus.PARTITIONED),
        Replica(replica_id="b", status=ReplicaStatus.PARTITIONED),
        Replica(replica_id="c"),
    ]})
    store = DistributedStateConsensus(cfg)
    result = store.propose(key="route", value="leo-a", writer_id="c")
    assert not result.committed
    assert store.get("route") is None


def test_merge_rejects_stale_version() -> None:
    store = DistributedStateConsensus(config())
    assert store.merge(StateUpdate(
        key="route",
        value="ground-a",
        version=StateVersion(epoch=0, sequence=2, writer_id="b"),
    ))
    assert not store.merge(StateUpdate(
        key="route",
        value="old",
        version=StateVersion(epoch=0, sequence=1, writer_id="a"),
    ))
    assert store.get("route").value == "ground-a"


def test_snapshot_fingerprint_is_deterministic() -> None:
    first = DistributedStateConsensus(config())
    second = DistributedStateConsensus(config())
    first.propose(key="route", value="uav-a", writer_id="a")
    second.propose(key="route", value="uav-a", writer_id="a")
    assert first.snapshot().deterministic_fingerprint == second.snapshot().deterministic_fingerprint
