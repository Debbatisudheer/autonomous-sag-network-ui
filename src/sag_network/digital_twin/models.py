from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.topology import NetworkTopology
from sag_network.domain.unified import UnifiedNetworkSnapshot
from sag_network.interference.model import InterferenceEvaluation


class DigitalTwinConfig(BaseModel):
    """Configuration for a deterministic in-memory digital twin."""

    twin_id: str = Field(min_length=1)
    network_name: str | None = Field(default=None, min_length=1)
    history_limit: int = Field(default=100, ge=1)
    enforce_monotonic_time: bool = True


class DigitalTwinSnapshot(BaseModel):
    """Synchronized digital representation of one SAG network instant."""

    snapshot_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    network_name: str = Field(min_length=1)
    unified_state: UnifiedNetworkSnapshot
    topology: NetworkTopology | None = None
    spectrum_state: SpectrumSchedulingSnapshot | None = None
    interference_evaluations: list[InterferenceEvaluation] = Field(default_factory=list)
    state_hash: str = Field(min_length=64, max_length=64)
    source: str = Field(min_length=1, default="simulation")
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_synchronized_timestamps(self) -> DigitalTwinSnapshot:
        if self.unified_state.timestamp_s != self.timestamp_s:
            raise ValueError("unified_state timestamp must match snapshot timestamp")
        if self.spectrum_state is not None and self.spectrum_state.timestamp_s != self.timestamp_s:
            raise ValueError("spectrum_state timestamp must match snapshot timestamp")
        return self


class TwinDelta(BaseModel):
    """Deterministic structural summary of changes between two twin snapshots."""

    previous_snapshot_id: str = Field(min_length=1)
    current_snapshot_id: str = Field(min_length=1)
    timestamp_delta_s: float = Field(ge=0)
    changed_user_ids: list[str] = Field(default_factory=list)
    changed_candidate_ids: list[str] = Field(default_factory=list)
    changed_topology_node_ids: list[str] = Field(default_factory=list)
    changed_topology_link_ids: list[str] = Field(default_factory=list)
    changed_spectrum_resource_ids: list[str] = Field(default_factory=list)
    interference_evaluation_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(
            self.changed_user_ids
            or self.changed_candidate_ids
            or self.changed_topology_node_ids
            or self.changed_topology_link_ids
            or self.changed_spectrum_resource_ids
            or self.interference_evaluation_changed
        )


def canonical_payload(snapshot: DigitalTwinSnapshot | dict[str, Any]) -> dict[str, Any]:
    """Return snapshot content excluding the derived hash field."""
    payload = (
        snapshot.model_dump(mode="json")
        if isinstance(snapshot, DigitalTwinSnapshot)
        else dict(snapshot)
    )
    payload.pop("state_hash", None)
    return payload
