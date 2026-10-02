from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from sag_network.digital_twin.models import (
    canonical_payload,
    DigitalTwinConfig,
    DigitalTwinSnapshot,
    TwinDelta,
)
from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.topology import NetworkTopology
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.interference.model import InterferenceEvaluation


class DigitalTwin:
    """Versioned deterministic state mirror for the SAG network.

    The twin consumes already-computed Ground/Air/Space observations and planning outputs. It does
    not replace the underlying physics or networking models.
    """

    def __init__(self, config: DigitalTwinConfig) -> None:
        self.config = config
        self._history: list[DigitalTwinSnapshot] = []

    @property
    def latest(self) -> DigitalTwinSnapshot | None:
        return self._history[-1] if self._history else None

    @property
    def history(self) -> tuple[DigitalTwinSnapshot, ...]:
        return tuple(self._history)

    @staticmethod
    def compute_state_hash(snapshot_data: DigitalTwinSnapshot) -> str:
        """Compute a stable SHA-256 digest from canonical JSON state."""
        payload = canonical_payload(snapshot_data)
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def create_snapshot(
        cls,
        *,
        snapshot_id: str,
        timestamp_s: float,
        network_name: str,
        unified_state: UnifiedNetworkSnapshot,
        topology: NetworkTopology | None = None,
        spectrum_state: SpectrumSchedulingSnapshot | None = None,
        interference_evaluations: Iterable[InterferenceEvaluation] = (),
        source: str = "simulation",
        metadata: dict[str, str] | None = None,
    ) -> DigitalTwinSnapshot:
        """Create a hashed snapshot from existing validated network state."""
        draft = DigitalTwinSnapshot(
            snapshot_id=snapshot_id,
            timestamp_s=timestamp_s,
            network_name=network_name,
            unified_state=unified_state,
            topology=topology,
            spectrum_state=spectrum_state,
            interference_evaluations=list(interference_evaluations),
            state_hash="0" * 64,
            source=source,
            metadata=metadata or {},
        )
        return draft.model_copy(update={"state_hash": cls.compute_state_hash(draft)})

    def sync(self, snapshot: DigitalTwinSnapshot) -> DigitalTwinSnapshot:
        """Validate and append a synchronized snapshot."""
        expected_hash = self.compute_state_hash(snapshot)
        if expected_hash != snapshot.state_hash:
            raise ValueError("digital twin snapshot state_hash does not match snapshot contents")
        if any(item.snapshot_id == snapshot.snapshot_id for item in self._history):
            raise ValueError(f"snapshot_id already exists in twin history: {snapshot.snapshot_id}")
        if (
            self.config.enforce_monotonic_time
            and self.latest is not None
            and snapshot.timestamp_s < self.latest.timestamp_s
        ):
            raise ValueError("snapshot timestamp must not move backwards")
        if (
            self.config.network_name is not None
            and snapshot.network_name != self.config.network_name
        ):
            raise ValueError("snapshot network_name does not match digital twin network_name")
        self._history.append(snapshot)
        if len(self._history) > self.config.history_limit:
            del self._history[: len(self._history) - self.config.history_limit]
        return snapshot

    def sync_many(self, snapshots: Iterable[DigitalTwinSnapshot]) -> None:
        """Synchronize an ordered collection of snapshots."""
        for snapshot in snapshots:
            self.sync(snapshot)

    def snapshot_at_or_before(self, timestamp_s: float) -> DigitalTwinSnapshot | None:
        """Return the newest retained snapshot not later than the supplied time."""
        candidates = [item for item in self._history if item.timestamp_s <= timestamp_s]
        return candidates[-1] if candidates else None

    def delta(self, previous: DigitalTwinSnapshot, current: DigitalTwinSnapshot) -> TwinDelta:
        """Compare two snapshots without modifying the twin history."""
        if current.timestamp_s < previous.timestamp_s:
            raise ValueError("current snapshot timestamp must not precede previous snapshot")

        previous_users = {item.user_id: item for item in previous.unified_state.associations}
        current_users = {item.user_id: item for item in current.unified_state.associations}
        user_ids = sorted(set(previous_users) | set(current_users))
        changed_users = [
            user_id
            for user_id in user_ids
            if previous_users.get(user_id) != current_users.get(user_id)
        ]

        def candidate_map(snapshot: DigitalTwinSnapshot) -> dict[str, object]:
            return {
                candidate.resource_id: candidate
                for association in snapshot.unified_state.associations
                for candidate in association.candidates
            }

        previous_candidates = candidate_map(previous)
        current_candidates = candidate_map(current)
        candidate_ids = sorted(set(previous_candidates) | set(current_candidates))
        changed_candidates = [
            resource_id
            for resource_id in candidate_ids
            if previous_candidates.get(resource_id) != current_candidates.get(resource_id)
        ]

        previous_nodes = (
            {}
            if previous.topology is None
            else {node.node_id: node for node in previous.topology.nodes}
        )
        current_nodes = (
            {}
            if current.topology is None
            else {node.node_id: node for node in current.topology.nodes}
        )
        node_ids = sorted(set(previous_nodes) | set(current_nodes))
        changed_nodes = [
            node_id
            for node_id in node_ids
            if previous_nodes.get(node_id) != current_nodes.get(node_id)
        ]

        previous_links = (
            {}
            if previous.topology is None
            else {link.link_id: link for link in previous.topology.links}
        )
        current_links = (
            {}
            if current.topology is None
            else {link.link_id: link for link in current.topology.links}
        )
        link_ids = sorted(set(previous_links) | set(current_links))
        changed_links = [
            link_id
            for link_id in link_ids
            if previous_links.get(link_id) != current_links.get(link_id)
        ]

        previous_resources = (
            {}
            if previous.spectrum_state is None
            else {item.resource_id: item for item in previous.spectrum_state.utilization}
        )
        current_resources = (
            {}
            if current.spectrum_state is None
            else {item.resource_id: item for item in current.spectrum_state.utilization}
        )
        resource_ids = sorted(set(previous_resources) | set(current_resources))
        changed_resources = [
            resource_id
            for resource_id in resource_ids
            if previous_resources.get(resource_id) != current_resources.get(resource_id)
        ]

        return TwinDelta(
            previous_snapshot_id=previous.snapshot_id,
            current_snapshot_id=current.snapshot_id,
            timestamp_delta_s=current.timestamp_s - previous.timestamp_s,
            changed_user_ids=changed_users,
            changed_candidate_ids=changed_candidates,
            changed_topology_node_ids=changed_nodes,
            changed_topology_link_ids=changed_links,
            changed_spectrum_resource_ids=changed_resources,
            interference_evaluation_changed=(
                previous.interference_evaluations != current.interference_evaluations
            ),
        )
