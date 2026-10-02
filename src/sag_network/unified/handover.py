from __future__ import annotations

from dataclasses import dataclass, field

from sag_network.domain.unified import UnifiedCandidate
from sag_network.domain.unified_handover import (
    UnifiedHandoverEvent,
    UnifiedHandoverEventType,
    UnifiedHandoverPolicy,
)


@dataclass
class UnifiedHandoverController:
    """Stateful deterministic controller for Ground-Air-Space handover."""

    policy: UnifiedHandoverPolicy = field(default_factory=UnifiedHandoverPolicy)
    serving_resource_id: str | None = None
    candidate_resource_id: str | None = None
    candidate_since_s: float | None = None

    def _event(
        self,
        *,
        timestamp_s: float,
        user_id: str,
        event_type: UnifiedHandoverEventType,
        previous: UnifiedCandidate | None,
        new: UnifiedCandidate | None,
        reason: str,
    ) -> UnifiedHandoverEvent:
        return UnifiedHandoverEvent(
            timestamp_s=timestamp_s,
            user_id=user_id,
            event_type=event_type,
            previous_resource_id=None if previous is None else previous.resource_id,
            previous_domain=None if previous is None else previous.domain,
            new_resource_id=None if new is None else new.resource_id,
            new_domain=None if new is None else new.domain,
            reason=reason,
        )

    @staticmethod
    def _choose_best(candidates: list[UnifiedCandidate]) -> UnifiedCandidate | None:
        available = [candidate for candidate in candidates if candidate.available]
        if not available:
            return None

        def sort_key(candidate: UnifiedCandidate) -> tuple[float, float, float, float, str]:
            return (
                candidate.link_margin_db,
                candidate.estimated_capacity_bps,
                -candidate.propagation_delay_ms,
                candidate.sinr_db,
                candidate.resource_id,
            )

        return max(available, key=sort_key)

    def update(
        self,
        *,
        user_id: str,
        timestamp_s: float,
        candidates: list[UnifiedCandidate],
    ) -> UnifiedHandoverEvent:
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")

        by_id = {candidate.resource_id: candidate for candidate in candidates}
        serving = (
            None
            if self.serving_resource_id is None
            else by_id.get(self.serving_resource_id)
        )
        best = self._choose_best(candidates)

        if serving is None:
            previous = (
                None
                if self.serving_resource_id is None
                else by_id.get(self.serving_resource_id)
            )
            self.candidate_resource_id = None
            self.candidate_since_s = None
            if best is None:
                self.serving_resource_id = None
                return self._event(
                    timestamp_s=timestamp_s,
                    user_id=user_id,
                    event_type=UnifiedHandoverEventType.NO_COVERAGE,
                    previous=previous,
                    new=None,
                    reason="no_available_resource",
                )
            self.serving_resource_id = best.resource_id
            event_type = (
                UnifiedHandoverEventType.ATTACH
                if previous is None
                else UnifiedHandoverEventType.HANDOVER
            )
            return self._event(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=event_type,
                previous=previous,
                new=best,
                reason="serving_unavailable_or_initial_attach",
            )

        if not serving.available:
            self.candidate_resource_id = None
            self.candidate_since_s = None
            if best is None:
                self.serving_resource_id = None
                return self._event(
                    timestamp_s=timestamp_s,
                    user_id=user_id,
                    event_type=UnifiedHandoverEventType.NO_COVERAGE,
                    previous=serving,
                    new=None,
                    reason="no_available_resource",
                )
            self.serving_resource_id = best.resource_id
            return self._event(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=UnifiedHandoverEventType.HANDOVER,
                previous=serving,
                new=best,
                reason="serving_unavailable",
            )

        if best is None:
            raise RuntimeError("best candidate must exist while the serving resource is available")

        if best.resource_id == serving.resource_id:
            self.candidate_resource_id = None
            self.candidate_since_s = None
            return self._event(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=UnifiedHandoverEventType.RETAIN,
                previous=serving,
                new=serving,
                reason="serving_remains_best_available",
            )

        improvement_db = best.link_margin_db - serving.link_margin_db
        if improvement_db < self.policy.hysteresis_db:
            self.candidate_resource_id = None
            self.candidate_since_s = None
            return self._event(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=UnifiedHandoverEventType.RETAIN,
                previous=serving,
                new=serving,
                reason="candidate_below_hysteresis",
            )

        if self.candidate_resource_id != best.resource_id:
            self.candidate_resource_id = best.resource_id
            self.candidate_since_s = timestamp_s

        if self.candidate_since_s is None:
            raise RuntimeError("candidate_since_s must be set when a handover candidate exists")

        if timestamp_s - self.candidate_since_s >= self.policy.time_to_trigger_s:
            previous = serving
            self.serving_resource_id = best.resource_id
            self.candidate_resource_id = None
            self.candidate_since_s = None
            return self._event(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=UnifiedHandoverEventType.HANDOVER,
                previous=previous,
                new=best,
                reason="candidate_exceeded_hysteresis_for_time_to_trigger",
            )

        return self._event(
            timestamp_s=timestamp_s,
            user_id=user_id,
            event_type=UnifiedHandoverEventType.RETAIN,
            previous=serving,
            new=serving,
            reason="candidate_in_time_to_trigger",
        )
