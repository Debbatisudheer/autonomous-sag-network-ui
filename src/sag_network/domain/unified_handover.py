from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from sag_network.domain.unified import NetworkDomain


class UnifiedHandoverEventType(str, Enum):
    ATTACH = "attach"
    RETAIN = "retain"
    HANDOVER = "handover"
    NO_COVERAGE = "no_coverage"


class UnifiedHandoverEvent(BaseModel):
    """Cross-domain mobility decision for one user."""

    timestamp_s: float = Field(ge=0)
    user_id: str = Field(min_length=1)
    event_type: UnifiedHandoverEventType
    previous_resource_id: str | None = None
    previous_domain: NetworkDomain | None = None
    new_resource_id: str | None = None
    new_domain: NetworkDomain | None = None
    reason: str = Field(min_length=1)


class UnifiedHandoverPolicy(BaseModel):
    """Deterministic baseline policy for cross-domain resource transitions."""

    hysteresis_db: float = Field(default=2.0, ge=0)
    time_to_trigger_s: float = Field(default=5.0, ge=0)


class UnifiedHandoverState(BaseModel):
    """State that can be persisted for one user's cross-domain controller."""

    serving_resource_id: str | None = None
    candidate_resource_id: str | None = None
    candidate_since_s: float | None = Field(default=None, ge=0)
