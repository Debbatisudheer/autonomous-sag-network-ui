from __future__ import annotations

from sag_network.domain.traffic import QoSMeasurement, QoSProfile, TrafficDemand
from sag_network.routing.engine import RouteResult

__all__ = ["measure_route_qos", "qos_is_satisfied", "qos_profile_is_valid", "required_service_rate"]


def measure_route_qos(route: RouteResult | None) -> QoSMeasurement | None:
    """Convert an existing route into end-to-end QoS measurements."""
    if route is None:
        return None
    return QoSMeasurement(
        capacity_bps=max(route.bottleneck_capacity_bps, 0.0),
        latency_ms=route.total_latency_ms,
        loss_rate=route.end_to_end_loss_rate,
    )


def required_service_rate(demand: TrafficDemand) -> float:
    """Return the bitrate required for full admission of a flow."""
    return max(demand.demand_bps, demand.qos.minimum_throughput_bps)


def qos_is_satisfied(*, demand: TrafficDemand, measurement: QoSMeasurement) -> bool:
    """Check throughput, latency, and loss against the flow's explicit requirements."""
    return (
        measurement.capacity_bps >= required_service_rate(demand)
        and measurement.latency_ms <= demand.qos.maximum_latency_ms
        and measurement.loss_rate <= demand.qos.maximum_loss_rate
    )


def qos_profile_is_valid(profile: QoSProfile) -> bool:
    """Validate the numeric bounds of a QoS profile for policy adapters."""
    return (
        profile.minimum_throughput_bps >= 0
        and profile.maximum_latency_ms > 0
        and 0 <= profile.maximum_loss_rate < 1
        and 0 <= profile.priority <= 100
    )
