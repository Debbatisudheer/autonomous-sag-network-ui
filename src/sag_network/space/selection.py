from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SatelliteCandidate:
    """Measured candidate state used by the deterministic baseline selector."""

    satellite_id: str
    available: bool
    link_margin_db: float
    elevation_deg: float
    shannon_capacity_bps: float
    propagation_delay_ms: float
    doppler_shift_hz: float
    predicted_loss_time_s: float | None = None


def select_best_satellite(candidates: list[SatelliteCandidate]) -> SatelliteCandidate | None:
    """Select a feasible satellite using an explicit safety-first baseline policy.

    This is intentionally deterministic and non-AI. It becomes the baseline against
    which later predictive/AI policies will be evaluated.
    """
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def sort_key(candidate: SatelliteCandidate) -> tuple[float, float, float, float, float]:
        time_to_loss = (
            float("inf")
            if candidate.predicted_loss_time_s is None
            else candidate.predicted_loss_time_s
        )
        return (
            candidate.link_margin_db,
            time_to_loss,
            candidate.shannon_capacity_bps,
            candidate.elevation_deg,
            -candidate.propagation_delay_ms,
        )

    return max(available, key=sort_key)
