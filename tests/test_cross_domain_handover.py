from __future__ import annotations

from sag_network.domain.unified import NetworkDomain, UnifiedCandidate
from sag_network.domain.unified_handover import (
    UnifiedHandoverEventType,
    UnifiedHandoverPolicy,
)
from sag_network.unified.handover import UnifiedHandoverController


def candidate(
    resource_id: str,
    domain: NetworkDomain,
    *,
    available: bool = True,
    margin: float = 10.0,
    capacity: float = 100e6,
    delay_ms: float = 5.0,
) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=domain,
        resource_type=f"{domain.value}_resource",
        available=available,
        distance_m=1_000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-96.0,
        sinr_db=16.0,
        link_margin_db=margin,
        shannon_capacity_bps=capacity,
        estimated_capacity_bps=capacity,
        propagation_delay_ms=delay_ms,
    )


def test_initial_attach_selects_available_cross_domain_resource() -> None:
    controller = UnifiedHandoverController()
    event = controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[
            candidate("ground-1", NetworkDomain.GROUND, margin=8.0),
            candidate("air-1", NetworkDomain.AIR, margin=12.0),
        ],
    )
    assert event.event_type is UnifiedHandoverEventType.ATTACH
    assert event.new_resource_id == "air-1"
    assert event.new_domain is NetworkDomain.AIR


def test_cross_domain_handover_requires_hysteresis_and_ttt() -> None:
    controller = UnifiedHandoverController(
        policy=UnifiedHandoverPolicy(hysteresis_db=2.0, time_to_trigger_s=10.0)
    )
    first = controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[
            candidate("ground-1", NetworkDomain.GROUND, margin=10.0),
            candidate("air-1", NetworkDomain.AIR, margin=11.0),
        ],
    )
    assert first.new_resource_id == "air-1"

    retained = controller.update(
        user_id="u1",
        timestamp_s=5.0,
        candidates=[
            candidate("air-1", NetworkDomain.AIR, margin=10.0),
            candidate("ground-1", NetworkDomain.GROUND, margin=14.0),
        ],
    )
    assert retained.event_type is UnifiedHandoverEventType.RETAIN

    handover_candidate = controller.update(
        user_id="u1",
        timestamp_s=10.0,
        candidates=[
            candidate("air-1", NetworkDomain.AIR, margin=8.0),
            candidate("ground-1", NetworkDomain.GROUND, margin=14.0),
        ],
    )
    assert handover_candidate.event_type is UnifiedHandoverEventType.RETAIN

    handover = controller.update(
        user_id="u1",
        timestamp_s=20.0,
        candidates=[
            candidate("air-1", NetworkDomain.AIR, margin=8.0),
            candidate("ground-1", NetworkDomain.GROUND, margin=14.0),
        ],
    )
    assert handover.event_type is UnifiedHandoverEventType.HANDOVER
    assert handover.previous_resource_id == "air-1"
    assert handover.new_resource_id == "ground-1"
    assert handover.new_domain is NetworkDomain.GROUND


def test_serving_failure_immediately_uses_available_other_domain() -> None:
    controller = UnifiedHandoverController()
    controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("air-1", NetworkDomain.AIR, margin=12.0)],
    )
    event = controller.update(
        user_id="u1",
        timestamp_s=30.0,
        candidates=[
            candidate("air-1", NetworkDomain.AIR, available=False, margin=-2.0),
            candidate("space-1", NetworkDomain.SPACE, margin=9.0),
        ],
    )
    assert event.event_type is UnifiedHandoverEventType.HANDOVER
    assert event.new_resource_id == "space-1"
    assert event.previous_domain is NetworkDomain.AIR
    assert event.new_domain is NetworkDomain.SPACE


def test_no_coverage_when_every_resource_is_unavailable() -> None:
    controller = UnifiedHandoverController()
    controller.update(
        user_id="u1",
        timestamp_s=0.0,
        candidates=[candidate("ground-1", NetworkDomain.GROUND)],
    )
    event = controller.update(
        user_id="u1",
        timestamp_s=1.0,
        candidates=[candidate("ground-1", NetworkDomain.GROUND, available=False, margin=-3.0)],
    )
    assert event.event_type is UnifiedHandoverEventType.NO_COVERAGE
    assert event.previous_resource_id == "ground-1"
    assert event.new_resource_id is None
