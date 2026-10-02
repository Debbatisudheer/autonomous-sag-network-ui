from __future__ import annotations

import math

from sag_network.channel.models import ChannelCondition, FadingDistribution
from sag_network.channel.randomness import complex_normal, normal_pair

C_MPS = 299_792_458.0


def maximum_doppler_hz(*, frequency_hz: float, relative_speed_mps: float) -> float:
    if frequency_hz <= 0 or relative_speed_mps < 0:
        raise ValueError("frequency_hz must be positive and relative_speed_mps must be non-negative")
    return frequency_hz * relative_speed_mps / C_MPS


def coherence_time_s(maximum_doppler_hz_value: float) -> float | None:
    if maximum_doppler_hz_value < 0:
        raise ValueError("maximum_doppler_hz_value must be non-negative")
    if maximum_doppler_hz_value == 0.0:
        return None
    return 0.423 / maximum_doppler_hz_value


def temporal_correlation(*, delta_t_s: float, coherence_time_s_value: float | None) -> float:
    if delta_t_s < 0:
        raise ValueError("delta_t_s must be non-negative")
    if coherence_time_s_value is None:
        return 1.0
    if delta_t_s == 0.0:
        return 1.0
    return math.exp(-delta_t_s / coherence_time_s_value)


def correlated_shadow_sample(
    *,
    seed: int,
    link_id: str,
    timestamp_s: float,
    sigma_db: float,
    previous_value_db: float | None,
    distance_step_m: float,
    decorrelation_distance_m: float,
) -> float:
    if sigma_db < 0 or previous_value_db is not None and distance_step_m < 0:
        raise ValueError("sigma_db and distance_step_m must be non-negative")
    if decorrelation_distance_m <= 0:
        raise ValueError("decorrelation_distance_m must be positive")
    if sigma_db == 0.0:
        return 0.0
    if previous_value_db is None:
        innovation, _ = normal_pair(seed, f"shadow:{link_id}:{timestamp_s:.9f}")
        return sigma_db * innovation
    rho = math.exp(-distance_step_m / decorrelation_distance_m)
    innovation, _ = normal_pair(seed, f"shadow:{link_id}:{timestamp_s:.9f}")
    return rho * previous_value_db + math.sqrt(max(1.0 - rho * rho, 0.0)) * sigma_db * innovation


def correlated_complex_sample(
    *,
    seed: int,
    link_id: str,
    timestamp_s: float,
    rho: float,
    previous_real: float | None,
    previous_imag: float | None,
    condition: ChannelCondition,
    rician_k_factor_db: float,
) -> tuple[float, float, FadingDistribution, float]:
    if not 0.0 <= rho <= 1.0:
        raise ValueError("rho must be between 0 and 1")
    if rician_k_factor_db < 0:
        raise ValueError("rician_k_factor_db must be non-negative")
    innovation_real, innovation_imag = complex_normal(
        seed, f"fading:{link_id}:{timestamp_s:.9f}"
    )
    if previous_real is None or previous_imag is None:
        gaussian_real = innovation_real
        gaussian_imag = innovation_imag
    else:
        innovation_scale = math.sqrt(max(1.0 - rho * rho, 0.0))
        gaussian_real = rho * previous_real + innovation_scale * innovation_real
        gaussian_imag = rho * previous_imag + innovation_scale * innovation_imag

    if condition is ChannelCondition.LOS:
        k_linear = 10.0 ** (rician_k_factor_db / 10.0)
        los_scale = math.sqrt(k_linear / (k_linear + 1.0))
        diffuse_scale = math.sqrt(1.0 / (k_linear + 1.0))
        real = los_scale + diffuse_scale * gaussian_real
        imag = diffuse_scale * gaussian_imag
        distribution = FadingDistribution.RICIAN
    else:
        real = gaussian_real
        imag = gaussian_imag
        distribution = FadingDistribution.RAYLEIGH

    power_linear = max(real * real + imag * imag, 1e-12)
    gain_db = 10.0 * math.log10(power_linear)
    return real, imag, distribution, gain_db
