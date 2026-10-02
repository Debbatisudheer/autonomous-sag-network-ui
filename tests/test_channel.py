import math

import pytest

from sag_network.channel.evaluator import (
    apply_channel_to_candidate,
    apply_channel_to_link,
    channel_fingerprint,
    NTNChannelModel,
)
from sag_network.channel.fading import coherence_time_s, maximum_doppler_hz, temporal_correlation
from sag_network.channel.models import (
    ChannelCondition,
    FadingDistribution,
    NTNBand,
    NTNChannelConfig,
    NTNChannelContext,
    NTNEnvironment,
    WeatherAttenuation,
)
from sag_network.channel.standard import los_probability, shadow_and_clutter, slant_airmass_factor
from sag_network.domain.link import LinkBudget
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate


def _context(**overrides: object) -> NTNChannelContext:
    values: dict[str, object] = {
        "link_id": "ue-01:sat-25544",
        "timestamp_s": 0.0,
        "elevation_deg": 80.0,
        "slant_range_m": 700_000.0,
        "frequency_hz": 3.5e9,
        "bandwidth_hz": 20e6,
        "relative_speed_mps": 7_500.0,
    }
    values.update(overrides)
    return NTNChannelContext(**values)


def _link() -> LinkBudget:
    return LinkBudget(
        distance_m=700_000.0,
        frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        free_space_path_loss_db=160.23,
        additional_path_loss_db=0.0,
        total_path_loss_db=160.23,
        rx_power_dbm=-90.0,
        noise_power_dbm=-100.0,
        interference_power_dbm=None,
        sinr_db=10.0,
        shannon_capacity_bps=69_250_000.0,
        required_sinr_db=5.0,
        link_margin_db=5.0,
        available=True,
    )


def _candidate() -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id="sat-25544",
        domain=NetworkDomain.SPACE,
        resource_type="leo_satellite",
        available=True,
        distance_m=700_000.0,
        rx_power_dbm=-90.0,
        noise_power_dbm=-100.0,
        sinr_db=10.0,
        link_margin_db=5.0,
        shannon_capacity_bps=69_250_000.0,
        estimated_capacity_bps=51_937_500.0,
        propagation_delay_ms=2.34,
    )


def test_3gpp_los_probability_uses_nearest_reference_angle() -> None:
    assert los_probability(elevation_deg=79.9, environment=NTNEnvironment.URBAN) == pytest.approx(0.968)
    assert los_probability(elevation_deg=80.1, environment=NTNEnvironment.URBAN) == pytest.approx(0.968)
    assert los_probability(elevation_deg=84.9, environment=NTNEnvironment.URBAN) == pytest.approx(0.968)
    assert los_probability(elevation_deg=85.1, environment=NTNEnvironment.URBAN) == pytest.approx(0.992)


def test_3gpp_shadow_and_clutter_tables_cover_s_and_ka_bands() -> None:
    s_sigma, s_clutter = shadow_and_clutter(
        elevation_deg=10.0,
        environment=NTNEnvironment.DENSE_URBAN,
        band=NTNBand.S_BAND,
        condition=ChannelCondition.NLOS,
    )
    ka_sigma, ka_clutter = shadow_and_clutter(
        elevation_deg=10.0,
        environment=NTNEnvironment.DENSE_URBAN,
        band=NTNBand.KA_BAND,
        condition=ChannelCondition.NLOS,
    )
    assert s_sigma == pytest.approx(15.5)
    assert s_clutter == pytest.approx(34.3)
    assert ka_sigma == pytest.approx(17.1)
    assert ka_clutter == pytest.approx(44.3)


def test_los_condition_has_zero_3gpp_clutter() -> None:
    sigma, clutter = shadow_and_clutter(
        elevation_deg=30.0,
        environment=NTNEnvironment.SUBURBAN_RURAL,
        band=NTNBand.S_BAND,
        condition=ChannelCondition.LOS,
    )
    assert sigma == pytest.approx(1.14)
    assert clutter == 0.0


def test_slant_airmass_factor_is_geometry_dependent() -> None:
    assert slant_airmass_factor(90.0) == pytest.approx(1.0)
    assert slant_airmass_factor(30.0) > slant_airmass_factor(90.0)


def test_doppler_and_coherence_are_frequency_and_speed_based() -> None:
    doppler = maximum_doppler_hz(frequency_hz=3.5e9, relative_speed_mps=7_500.0)
    assert doppler == pytest.approx(3.5e9 * 7_500.0 / 299_792_458.0, rel=1e-12)
    coherence = coherence_time_s(doppler)
    assert coherence is not None
    assert coherence == pytest.approx(0.423 / doppler)
    assert temporal_correlation(delta_t_s=0.0, coherence_time_s_value=coherence) == 1.0
    assert 0.0 < temporal_correlation(delta_t_s=coherence, coherence_time_s_value=coherence) < 1.0


def test_channel_realization_is_deterministic_for_same_seed_and_timestamp() -> None:
    config = NTNChannelConfig(seed=123, environment=NTNEnvironment.SUBURBAN_RURAL)
    first_model = NTNChannelModel(config)
    second_model = NTNChannelModel(config)
    first = first_model.evaluate(_context())
    second = second_model.evaluate(_context())
    assert first.model_dump() == second.model_dump()
    assert first.band is NTNBand.S_BAND
    assert first.fading_distribution is FadingDistribution.RICIAN or first.fading_distribution is FadingDistribution.RAYLEIGH


def test_channel_fingerprint_is_stable() -> None:
    first = NTNChannelModel(NTNChannelConfig(seed=123)).evaluate(_context())
    second = NTNChannelModel(NTNChannelConfig(seed=123)).evaluate(_context())
    assert channel_fingerprint(first) == channel_fingerprint(second)
    assert len(channel_fingerprint(first)) == 64


def test_same_timestamp_with_changed_context_is_rejected() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=123))
    model.evaluate(_context(timestamp_s=5.0))
    with pytest.raises(ValueError, match="identical channel context"):
        model.evaluate(_context(timestamp_s=5.0, elevation_deg=70.0))


def test_same_timestamp_is_idempotent() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=123))
    first = model.evaluate(_context(timestamp_s=5.0))
    second = model.evaluate(_context(timestamp_s=5.0))
    assert first.model_dump() == second.model_dump()


def test_backward_time_is_rejected_per_link() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=123))
    model.evaluate(_context(timestamp_s=10.0))
    with pytest.raises(ValueError, match="chronological"):
        model.evaluate(_context(timestamp_s=9.0))


def test_small_scale_fading_tracks_doppler_coherence() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=321))
    first = model.evaluate(_context(timestamp_s=0.0))
    second = model.evaluate(_context(timestamp_s=first.timestamp_s + 1e-6))
    if first.coherence_time_s is not None:
        correlation = temporal_correlation(
            delta_t_s=first.coherence_time_s,
            coherence_time_s_value=first.coherence_time_s,
        )
        assert correlation == pytest.approx(math.exp(-1.0))
        assert second.coherence_time_s == pytest.approx(first.coherence_time_s)
    assert math.isfinite(second.small_scale_fading_gain_db)


def test_nlos_uses_rayleigh_fading() -> None:
    model = NTNChannelModel(
        NTNChannelConfig(seed=1, environment=NTNEnvironment.DENSE_URBAN, los_correlation_time_s=0.001)
    )
    context = _context(elevation_deg=10.0)
    found_nlos = False
    for timestamp in range(1, 20):
        result = model.evaluate(context.model_copy(update={"timestamp_s": float(timestamp)}))
        if result.condition is ChannelCondition.NLOS:
            found_nlos = True
            assert result.fading_distribution is FadingDistribution.RAYLEIGH
            assert result.rician_k_factor_db == 0.0
            assert result.clutter_loss_db > 0.0
            break
    assert found_nlos is True


def test_weather_losses_scale_with_slant_geometry() -> None:
    config = NTNChannelConfig(
        seed=123,
        enable_small_scale_fading=False,
        weather=WeatherAttenuation(
            gas_specific_db_per_km=0.01,
            rain_specific_db_per_km=0.02,
            cloud_specific_db_per_km=0.03,
            scintillation_db=0.5,
            building_entry_loss_db=2.0,
        ),
    )
    model = NTNChannelModel(config)
    high = model.evaluate(_context(link_id="high", elevation_deg=90.0, slant_range_m=1_000_000.0))
    low = model.evaluate(_context(link_id="low", elevation_deg=30.0, slant_range_m=1_000_000.0))
    assert low.gas_loss_db > high.gas_loss_db
    assert low.rain_loss_db > high.rain_loss_db
    assert low.cloud_loss_db > high.cloud_loss_db
    assert high.scintillation_loss_db == pytest.approx(0.5)
    assert high.building_entry_loss_db == pytest.approx(2.0)


def test_channel_applies_deterministic_loss_and_fading_to_link_budget() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=123, enable_small_scale_fading=False))
    result = model.evaluate(
        _context(
            elevation_deg=90.0,
            slant_range_m=700_000.0,
        )
    )
    affected = apply_channel_to_link(link=_link(), result=result)
    assert affected.rx_power_dbm == pytest.approx(
        _link().rx_power_dbm - result.deterministic_loss_db + result.shadow_fading_db,
        abs=1e-9,
    )
    assert affected.total_path_loss_db >= _link().total_path_loss_db
    assert affected.sinr_db != _link().sinr_db


def test_channel_does_not_change_candidate_identity() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=123, enable_small_scale_fading=False))
    result = model.evaluate(_context())
    candidate = _candidate()
    affected = apply_channel_to_candidate(candidate=candidate, result=result, required_sinr_db=5.0)
    assert affected.resource_id == candidate.resource_id
    assert affected.domain is candidate.domain
    assert affected.resource_type == candidate.resource_type
    assert affected.estimated_capacity_bps <= affected.shannon_capacity_bps


def test_ka_band_is_selected_above_six_ghz() -> None:
    model = NTNChannelModel(NTNChannelConfig(seed=123, enable_small_scale_fading=False))
    result = model.evaluate(_context(frequency_hz=20e9))
    assert result.band is NTNBand.KA_BAND


def test_channel_result_contains_normalized_primary_tap() -> None:
    result = NTNChannelModel(NTNChannelConfig(seed=123)).evaluate(_context())
    assert len(result.taps) == 1
    assert result.taps[0].delay_ns == 0.0
    assert result.taps[0].relative_power_db == 0.0


def test_satellite_link_state_integrates_optional_channel_model() -> None:
    from sag_network.domain.link import PropagationLosses
    from sag_network.domain.models import GeoPoint
    from sag_network.domain.space import CartesianPoint
    from sag_network.space.link import satellite_link_state

    earth_radius_m = 6_378_137.0
    satellite_position = CartesianPoint(x_m=earth_radius_m + 700_000.0, y_m=0.0, z_m=0.0)
    satellite_velocity = CartesianPoint(x_m=0.0, y_m=7_500.0, z_m=0.0)
    result = satellite_link_state(
        timestamp_s=0.0,
        ground_station_id="ground-01",
        ground_position=GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0),
        satellite_position_ecef=satellite_position,
        satellite_velocity_ecef=satellite_velocity,
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30.0,
        tx_gain_dbi=15.0,
        rx_gain_dbi=0.0,
        noise_figure_db=5.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=0.0,
            rain_db=0.0,
            polarization_db=0.5,
            implementation_db=0.5,
        ),
        required_sinr_db=5.0,
        minimum_elevation_deg=10.0,
        channel_model=NTNChannelModel(
            NTNChannelConfig(seed=99, enable_small_scale_fading=False)
        ),
        channel_link_id="ground-01:sat-01",
    )
    assert "channel_condition" in result
    assert "shadow_fading_db" in result
    assert "maximum_doppler_hz" in result
    assert result["available"] in {True, False}


def test_invalid_context_rejected() -> None:
    with pytest.raises(ValueError):
        NTNChannelContext(
            link_id="x",
            timestamp_s=0.0,
            elevation_deg=91.0,
            slant_range_m=1.0,
            frequency_hz=1.0,
            bandwidth_hz=1.0,
            relative_speed_mps=0.0,
        )
