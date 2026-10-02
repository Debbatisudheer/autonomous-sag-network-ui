from __future__ import annotations

from datetime import datetime, UTC
from math import sqrt
from typing import Protocol

from sag_network.ephemeris.models import EphemerisSimulationConfig, RealSatelliteState


class AbsoluteStateProvider(Protocol):
    """Contract for absolute UTC satellite state providers."""

    def state_at(self, timestamp_utc: datetime) -> RealSatelliteState:
        ...


class SimulationStateProvider(Protocol):
    """Contract for relative simulation-time satellite state providers."""

    def state_at(self, timestamp_s: float) -> RealSatelliteState:
        ...


class SimulationEphemerisAdapter:
    """Expose an absolute UTC SGP4 provider on the existing relative simulation clock."""

    def __init__(self, provider: AbsoluteStateProvider, config: EphemerisSimulationConfig) -> None:
        self.provider = provider
        self.config = config

    def state_at(self, timestamp_s: float) -> RealSatelliteState:
        if timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")
        simulation_epoch = self.config.simulation_epoch_utc.astimezone(UTC)
        absolute_time = datetime.fromtimestamp(
            simulation_epoch.timestamp() + timestamp_s, tz=UTC
        )
        state = self.provider.state_at(absolute_time)
        if abs(state.elapsed_since_epoch_s) > self.config.max_propagation_age_s:
            raise ValueError("ephemeris propagation exceeds configured freshness horizon")
        return state

    @staticmethod
    def speed_m_s(state: RealSatelliteState) -> float:
        vx, vy, vz = state.velocity_ecef_m_s
        return sqrt(vx**2 + vy**2 + vz**2)
