from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class HandoverEventType(str, Enum):
    ATTACH = "attach"
    RETAIN = "retain"
    HANDOVER = "handover"
    NO_COVERAGE = "no_coverage"


class HandoverEvent(BaseModel):
    """Deterministic mobility-management decision emitted for one user."""

    timestamp_s: float = Field(ge=0)
    user_id: str = Field(min_length=1)
    event_type: HandoverEventType
    previous_satellite_id: str | None = None
    new_satellite_id: str | None = None
    reason: str = Field(min_length=1)
