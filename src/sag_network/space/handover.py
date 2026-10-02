from __future__ import annotations

from dataclasses import dataclass

from sag_network.domain.handover import HandoverEvent, HandoverEventType
from sag_network.space.selection import SatelliteCandidate, select_best_satellite


@dataclass
class HandoverController:
    """Deterministic baseline handover controller with hysteresis and time-to-trigger."""

    hysteresis_db: float = 2.0
    time_to_trigger_s: float = 5.0
    serving_satellite_id: str | None = None
    candidate_satellite_id: str | None = None
    candidate_since_s: float | None = None

    def __post_init__(self) -> None:
        if self.hysteresis_db < 0:
            raise ValueError("hysteresis_db must be non-negative")
        if self.time_to_trigger_s < 0:
            raise ValueError("time_to_trigger_s must be non-negative")

    def update(
        self,
        *,
        user_id: str,
        timestamp_s: float,
        candidates: list[SatelliteCandidate],
    ) -> HandoverEvent:
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")

        by_id = {candidate.satellite_id: candidate for candidate in candidates}
        serving = None if self.serving_satellite_id is None else by_id.get(self.serving_satellite_id)
        best = select_best_satellite(candidates)

        if serving is None:
            self.candidate_satellite_id = None
            self.candidate_since_s = None
            previous = self.serving_satellite_id
            if best is None:
                self.serving_satellite_id = None
                return HandoverEvent(
                    timestamp_s=timestamp_s,
                    user_id=user_id,
                    event_type=HandoverEventType.NO_COVERAGE,
                    previous_satellite_id=previous,
                    new_satellite_id=None,
                    reason="no_available_satellite",
                )
            self.serving_satellite_id = best.satellite_id
            event_type = HandoverEventType.ATTACH if previous is None else HandoverEventType.HANDOVER
            return HandoverEvent(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=event_type,
                previous_satellite_id=previous,
                new_satellite_id=best.satellite_id,
                reason="serving_unavailable_or_initial_attach",
            )

        if not serving.available:
            self.candidate_satellite_id = None
            self.candidate_since_s = None
            previous = self.serving_satellite_id
            if best is None:
                self.serving_satellite_id = None
                return HandoverEvent(
                    timestamp_s=timestamp_s,
                    user_id=user_id,
                    event_type=HandoverEventType.NO_COVERAGE,
                    previous_satellite_id=previous,
                    new_satellite_id=None,
                    reason="no_available_satellite",
                )
            self.serving_satellite_id = best.satellite_id
            event_type = HandoverEventType.ATTACH if previous is None else HandoverEventType.HANDOVER
            return HandoverEvent(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=event_type,
                previous_satellite_id=previous,
                new_satellite_id=best.satellite_id,
                reason="serving_unavailable_or_initial_attach",
            )

        if best is None:
            raise RuntimeError("best satellite must exist when serving satellite is available")

        if best.satellite_id == serving.satellite_id:
            self.candidate_satellite_id = None
            self.candidate_since_s = None
            return HandoverEvent(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=HandoverEventType.RETAIN,
                previous_satellite_id=serving.satellite_id,
                new_satellite_id=serving.satellite_id,
                reason="serving_remains_best_available",
            )

        improvement_db = best.link_margin_db - serving.link_margin_db
        if improvement_db < self.hysteresis_db:
            self.candidate_satellite_id = None
            self.candidate_since_s = None
            return HandoverEvent(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=HandoverEventType.RETAIN,
                previous_satellite_id=serving.satellite_id,
                new_satellite_id=serving.satellite_id,
                reason="candidate_below_hysteresis",
            )

        if self.candidate_satellite_id != best.satellite_id:
            self.candidate_satellite_id = best.satellite_id
            self.candidate_since_s = timestamp_s

        assert self.candidate_since_s is not None
        if timestamp_s - self.candidate_since_s >= self.time_to_trigger_s:
            previous = self.serving_satellite_id
            self.serving_satellite_id = best.satellite_id
            self.candidate_satellite_id = None
            self.candidate_since_s = None
            return HandoverEvent(
                timestamp_s=timestamp_s,
                user_id=user_id,
                event_type=HandoverEventType.HANDOVER,
                previous_satellite_id=previous,
                new_satellite_id=best.satellite_id,
                reason="candidate_exceeded_hysteresis_for_time_to_trigger",
            )

        return HandoverEvent(
            timestamp_s=timestamp_s,
            user_id=user_id,
            event_type=HandoverEventType.RETAIN,
            previous_satellite_id=serving.satellite_id,
            new_satellite_id=serving.satellite_id,
            reason="candidate_in_time_to_trigger",
        )
