from __future__ import annotations

import hashlib
import json
import math

from sag_network.channel.fading import (
    coherence_time_s,
    correlated_complex_sample,
    correlated_shadow_sample,
    maximum_doppler_hz,
    temporal_correlation,
)
from sag_network.channel.models import (
    ChannelCondition,
    FadingDistribution,
    NTNChannelConfig,
    NTNChannelContext,
    NTNChannelResult,
    PowerDelayTap,
)
from sag_network.channel.randomness import uniform
from sag_network.channel.standard import (
    los_probability,
    select_band,
    shadow_and_clutter,
    slant_airmass_factor,
)
from sag_network.domain.link import LinkBudget
from sag_network.domain.unified import UnifiedCandidate
from sag_network.physics.link_budget import shannon_capacity_bps, sinr_db


class NTNChannelModel:
    """Stateful deterministic channel realization engine for LEO/HAPS-style NTN links."""

    def __init__(self, config: NTNChannelConfig | None = None) -> None:
        self.config = config or NTNChannelConfig()
        self._last_timestamp_s: dict[str, float] = {}
        self._last_condition: dict[str, ChannelCondition] = {}
        self._last_shadow_db: dict[str, float] = {}
        self._last_fading: dict[str, tuple[float, float]] = {}
        self._last_range_m: dict[str, float] = {}
        self._last_result: dict[str, NTNChannelResult] = {}
        self._last_context: dict[str, NTNChannelContext] = {}

    def _condition(
        self,
        *,
        context: NTNChannelContext,
        probability: float,
    ) -> ChannelCondition:
        previous = self._last_condition.get(context.link_id)
        if previous is None:
            draw = uniform(self.config.seed, f"los:{context.link_id}:{context.timestamp_s:.9f}")
            return ChannelCondition.LOS if draw < probability else ChannelCondition.NLOS

        previous_timestamp = self._last_timestamp_s[context.link_id]
        delta_t_s = context.timestamp_s - previous_timestamp
        persistence = math.exp(-delta_t_s / self.config.los_correlation_time_s)
        if previous is ChannelCondition.LOS:
            probability_los = probability + (1.0 - probability) * persistence
        else:
            probability_los = probability * (1.0 - persistence)
        draw = uniform(self.config.seed, f"los:{context.link_id}:{context.timestamp_s:.9f}")
        return ChannelCondition.LOS if draw < probability_los else ChannelCondition.NLOS

    def evaluate(self, context: NTNChannelContext) -> NTNChannelResult:
        previous_timestamp = self._last_timestamp_s.get(context.link_id)
        if previous_timestamp is not None and context.timestamp_s < previous_timestamp:
            raise ValueError("channel evaluations must be chronological per link_id")
        if previous_timestamp is not None and context.timestamp_s == previous_timestamp:
            previous_context = self._last_context[context.link_id]
            if previous_context != context:
                raise ValueError("same timestamp requires identical channel context per link_id")
            return self._last_result[context.link_id]

        band = self.config.band or select_band(context.frequency_hz)
        probability = los_probability(
            elevation_deg=context.elevation_deg,
            environment=self.config.environment,
        )
        condition = self._condition(context=context, probability=probability)
        shadow_sigma_db, clutter_loss_db = shadow_and_clutter(
            elevation_deg=context.elevation_deg,
            environment=self.config.environment,
            band=band,
            condition=condition,
        )

        previous_shadow = self._last_shadow_db.get(context.link_id)
        distance_step_m = 0.0
        if context.link_id in self._last_range_m:
            distance_step_m = abs(context.slant_range_m - self._last_range_m[context.link_id])
        shadow_db = 0.0
        if self.config.enable_shadow_fading:
            shadow_db = correlated_shadow_sample(
                seed=self.config.seed,
                link_id=context.link_id,
                timestamp_s=context.timestamp_s,
                sigma_db=shadow_sigma_db,
                previous_value_db=previous_shadow,
                distance_step_m=distance_step_m,
                decorrelation_distance_m=self.config.shadow_decorrelation_distance_m,
            )

        max_doppler = maximum_doppler_hz(
            frequency_hz=context.frequency_hz,
            relative_speed_mps=context.relative_speed_mps,
        )
        coherence = coherence_time_s(max_doppler)
        rho = 1.0
        if previous_timestamp is not None:
            rho = temporal_correlation(
                delta_t_s=context.timestamp_s - previous_timestamp,
                coherence_time_s_value=coherence,
            )
        previous_fading = self._last_fading.get(context.link_id)
        previous_condition = self._last_condition.get(context.link_id)
        if previous_fading is not None and previous_condition is not None and previous_condition is not condition:
            previous_fading = None
        if self.config.enable_small_scale_fading:
            fading_real, fading_imag, distribution, fading_gain_db = correlated_complex_sample(
                seed=self.config.seed,
                link_id=context.link_id,
                timestamp_s=context.timestamp_s,
                rho=rho,
                previous_real=None if previous_fading is None else previous_fading[0],
                previous_imag=None if previous_fading is None else previous_fading[1],
                condition=condition,
                rician_k_factor_db=self.config.rician_k_factor_db,
            )
        else:
            distribution = (
                FadingDistribution.RICIAN
                if condition is ChannelCondition.LOS
                else FadingDistribution.RAYLEIGH
            )
            fading_real = 1.0
            fading_imag = 0.0
            fading_gain_db = 0.0

        gas_loss_db = 0.0
        rain_loss_db = 0.0
        cloud_loss_db = 0.0
        scintillation_loss_db = 0.0
        building_entry_loss_db = 0.0
        if self.config.enable_weather_attenuation:
            slant_factor = slant_airmass_factor(context.elevation_deg)
            slant_km = context.slant_range_m / 1_000.0
            weather = self.config.weather
            gas_loss_db = weather.gas_specific_db_per_km * slant_km * slant_factor
            rain_loss_db = weather.rain_specific_db_per_km * slant_km * slant_factor
            cloud_loss_db = weather.cloud_specific_db_per_km * slant_km * slant_factor
            scintillation_loss_db = weather.scintillation_db
            building_entry_loss_db = weather.building_entry_loss_db

        effective_clutter_loss_db = clutter_loss_db if self.config.enable_3gpp_large_scale else 0.0
        deterministic_loss_db = (
            effective_clutter_loss_db
            + gas_loss_db
            + rain_loss_db
            + cloud_loss_db
            + scintillation_loss_db
            + building_entry_loss_db
        )
        taps = [
            PowerDelayTap(
                delay_ns=0.0,
                relative_power_db=0.0,
                distribution=distribution,
            )
        ]

        result = NTNChannelResult(
            link_id=context.link_id,
            timestamp_s=context.timestamp_s,
            elevation_deg=context.elevation_deg,
            slant_range_m=context.slant_range_m,
            frequency_hz=context.frequency_hz,
            bandwidth_hz=context.bandwidth_hz,
            relative_speed_mps=context.relative_speed_mps,
            band=band,
            environment=self.config.environment,
            los_probability=probability,
            condition=condition,
            shadow_sigma_db=shadow_sigma_db,
            shadow_fading_db=shadow_db,
            clutter_loss_db=effective_clutter_loss_db,
            gas_loss_db=gas_loss_db,
            rain_loss_db=rain_loss_db,
            cloud_loss_db=cloud_loss_db,
            scintillation_loss_db=scintillation_loss_db,
            building_entry_loss_db=building_entry_loss_db,
            deterministic_loss_db=deterministic_loss_db,
            fading_distribution=distribution,
            rician_k_factor_db=self.config.rician_k_factor_db if distribution.value == "rician" else 0.0,
            small_scale_fading_gain_db=fading_gain_db,
            channel_gain_real=fading_real,
            channel_gain_imag=fading_imag,
            coherence_time_s=coherence,
            maximum_doppler_hz=max_doppler,
            taps=taps,
        )

        self._last_timestamp_s[context.link_id] = context.timestamp_s
        self._last_condition[context.link_id] = condition
        self._last_shadow_db[context.link_id] = shadow_db
        self._last_fading[context.link_id] = (fading_real, fading_imag)
        self._last_range_m[context.link_id] = context.slant_range_m
        self._last_result[context.link_id] = result
        self._last_context[context.link_id] = context
        return result


def apply_channel_to_link(*, link: LinkBudget, result: NTNChannelResult) -> LinkBudget:
    """Apply channel attenuation and fading while preserving baseline link-budget semantics."""
    desired_rx_power_dbm = (
        link.rx_power_dbm
        - result.deterministic_loss_db
        + result.shadow_fading_db
        + result.small_scale_fading_gain_db
    )
    measured_sinr_db = sinr_db(
        desired_rx_power_dbm,
        link.noise_power_dbm,
        link.interference_power_dbm,
    )
    capacity_bps = shannon_capacity_bps(link.bandwidth_hz, measured_sinr_db)
    margin_db = measured_sinr_db - link.required_sinr_db
    return link.model_copy(
        update={
            "additional_path_loss_db": link.additional_path_loss_db + result.deterministic_loss_db,
            "total_path_loss_db": link.total_path_loss_db + result.deterministic_loss_db,
            "rx_power_dbm": desired_rx_power_dbm,
            "sinr_db": measured_sinr_db,
            "shannon_capacity_bps": capacity_bps,
            "link_margin_db": margin_db,
            "available": link.available and margin_db >= 0.0,
        }
    )


def apply_channel_to_candidate(
    *,
    candidate: UnifiedCandidate,
    result: NTNChannelResult,
    required_sinr_db: float,
) -> UnifiedCandidate:
    """Apply a channel realization to a unified candidate without changing resource identity."""
    desired_rx_power_dbm = (
        candidate.rx_power_dbm
        - result.deterministic_loss_db
        + result.shadow_fading_db
        + result.small_scale_fading_gain_db
    )
    measured_sinr_db = sinr_db(
        desired_rx_power_dbm,
        candidate.noise_power_dbm,
        None,
    )
    capacity_bps = shannon_capacity_bps(result.bandwidth_hz, measured_sinr_db)
    # UnifiedCandidate does not carry scheduler configuration; preserve its existing efficiency ratio.
    baseline_capacity = candidate.shannon_capacity_bps
    if baseline_capacity > 0.0:
        estimated_ratio = candidate.estimated_capacity_bps / baseline_capacity
    else:
        estimated_ratio = 0.0
    margin_db = measured_sinr_db - required_sinr_db
    return candidate.model_copy(
        update={
            "rx_power_dbm": desired_rx_power_dbm,
            "sinr_db": measured_sinr_db,
            "link_margin_db": margin_db,
            "shannon_capacity_bps": capacity_bps,
            "estimated_capacity_bps": capacity_bps * max(min(estimated_ratio, 1.0), 0.0),
            "available": candidate.available and margin_db >= 0.0,
        }
    )


def channel_fingerprint(result: NTNChannelResult) -> str:
    """Return a deterministic SHA-256 fingerprint for one channel realization."""
    payload = json.dumps(
        result.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
