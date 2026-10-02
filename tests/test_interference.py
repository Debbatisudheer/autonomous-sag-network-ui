import math

import pytest

from sag_network.domain.link import LinkBudget
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate
from sag_network.interference.evaluator import (
    apply_channel_effects_to_candidate,
    apply_channel_effects_to_link,
    frequency_overlap_fraction,
    interference_contribution_watts,
)
from sag_network.interference.model import ChannelEffectProfile, InterferenceSource


def _source(**overrides: object) -> InterferenceSource:
    values: dict[str, object] = {
        "source_id": "int-a",
        "carrier_frequency_hz": 3_500_000_000.0,
        "bandwidth_hz": 20_000_000.0,
        "distance_m": 1_000.0,
        "tx_power_dbm": 0.0,
    }
    values.update(overrides)
    return InterferenceSource(**values)


def _link() -> LinkBudget:
    return LinkBudget(
        distance_m=1_000.0,
        frequency_hz=3_500_000_000.0,
        bandwidth_hz=20_000_000.0,
        free_space_path_loss_db=103.33,
        additional_path_loss_db=0.0,
        total_path_loss_db=103.33,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        interference_power_dbm=None,
        sinr_db=30.0,
        shannon_capacity_bps=199_315_685.693,
        required_sinr_db=5.0,
        link_margin_db=25.0,
        available=True,
    )


def _candidate() -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id="uav-a",
        domain=NetworkDomain.AIR,
        resource_type="uav",
        available=True,
        distance_m=1_000.0,
        rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        sinr_db=30.0,
        link_margin_db=25.0,
        shannon_capacity_bps=199_315_685.693,
        estimated_capacity_bps=149_486_764.27,
        propagation_delay_ms=0.0033,
    )


def test_full_band_overlap_is_one():
    assert math.isclose(
        frequency_overlap_fraction(
            desired_frequency_hz=3.5e9,
            desired_bandwidth_hz=20e6,
            interferer_frequency_hz=3.5e9,
            interferer_bandwidth_hz=20e6,
        ),
        1.0,
    )


def test_non_overlapping_bands_have_no_interference():
    watts, contribution = interference_contribution_watts(
        source=_source(carrier_frequency_hz=3.6e9),
        desired_frequency_hz=3.5e9,
        desired_bandwidth_hz=20e6,
    )
    assert watts == 0.0
    assert contribution.effective_power_dbm is None
    assert contribution.overlap_fraction == 0.0


def test_interference_power_is_aggregated_in_linear_domain():
    first = _source(source_id="a", tx_power_dbm=0.0)
    second = _source(source_id="b", tx_power_dbm=0.0)
    baseline = apply_channel_effects_to_link(
        link=_link(),
        channel_effects=ChannelEffectProfile(),
        interferers=[first, second],
    )
    assert baseline.interference_power_dbm is not None
    one = apply_channel_effects_to_link(
        link=_link(),
        channel_effects=ChannelEffectProfile(),
        interferers=[first],
    )
    assert one.interference_power_dbm is not None
    assert baseline.interference_power_dbm == pytest.approx(
        one.interference_power_dbm + 3.0103, abs=0.02
    )


def test_channel_loss_reduces_received_power_and_capacity():
    affected = apply_channel_effects_to_link(
        link=_link(),
        channel_effects=ChannelEffectProfile(additional_loss_db=10.0),
        interferers=[],
    )
    assert affected.rx_power_dbm == pytest.approx(-80.0)
    assert affected.total_path_loss_db == pytest.approx(113.33)
    assert affected.shannon_capacity_bps < _link().shannon_capacity_bps
    assert affected.link_margin_db < _link().link_margin_db


def test_interference_can_make_candidate_unavailable():
    strong = _source(tx_power_dbm=30.0, distance_m=100.0)
    affected = apply_channel_effects_to_candidate(
        candidate=_candidate(),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        required_sinr_db=5.0,
        channel_effects=ChannelEffectProfile(),
        interferers=[strong],
    )
    assert affected.sinr_db < _candidate().sinr_db
    assert affected.link_margin_db < _candidate().link_margin_db
    assert affected.estimated_capacity_bps < _candidate().estimated_capacity_bps
    assert affected.available is False


def test_inactive_interferer_preserves_baseline():
    affected = apply_channel_effects_to_candidate(
        candidate=_candidate(),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        required_sinr_db=5.0,
        channel_effects=ChannelEffectProfile(),
        interferers=[_source(active=False)],
    )
    assert affected.sinr_db == pytest.approx(_candidate().sinr_db)
    assert affected.shannon_capacity_bps == pytest.approx(_candidate().shannon_capacity_bps)
    assert affected.estimated_capacity_bps == pytest.approx(_candidate().estimated_capacity_bps)
    assert affected.available is True


def test_degraded_candidate_changes_phase13_spectrum_admission():
    from sag_network.domain.resource import SpectrumResource
    from sag_network.domain.traffic import QoSProfile, ServiceClass, TrafficDemand
    from sag_network.resource.scheduler import schedule_spectrum

    demand = TrafficDemand(
        flow_id="flow-01",
        user_id="user-01",
        demand_bps=100e6,
        qos=QoSProfile(
            service_class=ServiceClass.STREAMING,
            minimum_throughput_bps=100e6,
            maximum_latency_ms=100.0,
            maximum_loss_rate=0.01,
            priority=50,
        ),
    )
    resource = SpectrumResource(
        resource_id="uav-a",
        bandwidth_hz=20e6,
        resource_block_bandwidth_hz=20e6,
        scheduler_efficiency=1.0,
    )
    baseline = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand],
        candidates_by_user={"user-01": [_candidate()]},
        resources={"uav-a": resource},
    )
    assert baseline.allocations[0].admitted is True

    degraded = apply_channel_effects_to_candidate(
        candidate=_candidate(),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        required_sinr_db=5.0,
        channel_effects=ChannelEffectProfile(additional_loss_db=8.0),
        interferers=[_source(tx_power_dbm=20.0, distance_m=100.0)],
    )
    affected = schedule_spectrum(
        timestamp_s=0.0,
        demands=[demand],
        candidates_by_user={"user-01": [degraded]},
        resources={"uav-a": resource},
    )
    assert affected.allocations[0].admitted is False
