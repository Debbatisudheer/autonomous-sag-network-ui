from __future__ import annotations

import json

from sag_network.consensus import (
    ConsensusConfig,
    DistributedStateConsensus,
    Replica,
    ReplicaStatus,
)


def main() -> None:
    config = ConsensusConfig(
        cluster_id="sag-consensus-a",
        replicas=[
            Replica(replica_id="edge-a"),
            Replica(replica_id="edge-b"),
            Replica(replica_id="edge-c"),
            Replica(replica_id="edge-d", status=ReplicaStatus.PARTITIONED),
            Replica(replica_id="edge-e", status=ReplicaStatus.PARTITIONED),
        ],
    )
    consensus = DistributedStateConsensus(config)
    committed = consensus.propose(key="serving-resource", value="uav-a", writer_id="edge-a")
    partitioned = DistributedStateConsensus(
        config.model_copy(update={"replicas": [
            Replica(replica_id="edge-a", status=ReplicaStatus.PARTITIONED),
            Replica(replica_id="edge-b", status=ReplicaStatus.PARTITIONED),
            Replica(replica_id="edge-c", status=ReplicaStatus.PARTITIONED),
            Replica(replica_id="edge-d", status=ReplicaStatus.PARTITIONED),
            Replica(replica_id="edge-e"),
        ]})
    ).propose(key="serving-resource", value="leo-a", writer_id="edge-e")
    snapshot = consensus.snapshot()
    print(json.dumps({
        "name": "Distributed State & Consensus",
        "phase": "41",
        "status": "pass" if committed.committed and not partitioned.committed else "fail",
        "cluster_id": snapshot.cluster_id,
        "total_replicas": snapshot.total_replicas,
        "available_replicas": snapshot.available_replicas,
        "quorum": snapshot.quorum,
        "committed_keys": snapshot.committed_keys,
        "commit_acknowledgements": committed.acknowledgements,
        "partition_acknowledgements": partitioned.acknowledgements,
        "partition_safe": not partitioned.committed,
        "state_fingerprint": snapshot.deterministic_fingerprint,
        "fixture": "synthetic offline consensus fixture",
        "network_mutation": False,
    }, indent=2))


if __name__ == "__main__":
    main()
