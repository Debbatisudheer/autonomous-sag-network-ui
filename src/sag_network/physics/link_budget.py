from __future__ import annotations

import math

from sag_network.domain.link import LinkBudget, PropagationLosses

C_MPS = 299_792_458.0
K_BOLTZMANN_J_PER_K = 1.380649e-23
REFERENCE_TEMP_K = 290.0


def free_space_path_loss_db(distance_m: float, frequency_hz: float) -> float:
    """Friis free-space path loss in dB."""
    if distance_m <= 0 or frequency_hz <= 0:
        raise ValueError("distance_m and frequency_hz must be positive")
    wavelength_m = C_MPS / frequency_hz
    return 20.0 * math.log10(4.0 * math.pi * distance_m / wavelength_m)


def thermal_noise_power_dbm(
    bandwidth_hz: float,
    noise_figure_db: float = 0.0,
    temperature_k: float = REFERENCE_TEMP_K,
) -> float:
    """Thermal noise power in dBm including receiver noise figure."""
    if bandwidth_hz <= 0 or temperature_k <= 0:
        raise ValueError("bandwidth_hz and temperature_k must be positive")
    watts = K_BOLTZMANN_J_PER_K * temperature_k * bandwidth_hz
    return 10.0 * math.log10(watts / 1e-3) + noise_figure_db


def received_power_dbm(
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    path_loss_db: float,
) -> float:
    return tx_power_dbm + tx_gain_dbi + rx_gain_dbi - path_loss_db


def sinr_db(signal_dbm: float, noise_dbm: float, interference_dbm: float | None = None) -> float:
    """Compute SINR in dB from signal/noise/interference powers in dBm."""
    signal_w = 10 ** ((signal_dbm - 30) / 10)
    noise_w = 10 ** ((noise_dbm - 30) / 10)
    interference_w = 0.0 if interference_dbm is None else 10 ** ((interference_dbm - 30) / 10)
    denominator_w = noise_w + interference_w
    ratio = signal_w / denominator_w
    return 10.0 * math.log10(ratio)


def shannon_capacity_bps(bandwidth_hz: float, sinr_db_value: float) -> float:
    """Return Shannon's idealized capacity upper bound."""
    if bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz must be positive")
    sinr_linear = 10 ** (sinr_db_value / 10)
    return bandwidth_hz * math.log2(1.0 + sinr_linear)


def link_budget(
    *,
    distance_m: float,
    frequency_hz: float,
    bandwidth_hz: float,
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    noise_figure_db: float,
    propagation_losses: PropagationLosses,
    interference_power_dbm: float | None = None,
    required_sinr_db: float = 0.0,
) -> LinkBudget:
    """Calculate a transparent radio-link budget with explicit non-FSPL losses."""
    fspl_db = free_space_path_loss_db(distance_m, frequency_hz)
    total_loss_db = fspl_db + propagation_losses.total_db
    rx_dbm = received_power_dbm(tx_power_dbm, tx_gain_dbi, rx_gain_dbi, total_loss_db)
    noise_dbm = thermal_noise_power_dbm(bandwidth_hz, noise_figure_db)
    measured_sinr_db = sinr_db(rx_dbm, noise_dbm, interference_power_dbm)
    capacity_bps = shannon_capacity_bps(bandwidth_hz, measured_sinr_db)
    margin_db = measured_sinr_db - required_sinr_db
    return LinkBudget(
        distance_m=distance_m,
        frequency_hz=frequency_hz,
        bandwidth_hz=bandwidth_hz,
        free_space_path_loss_db=fspl_db,
        additional_path_loss_db=propagation_losses.total_db,
        total_path_loss_db=total_loss_db,
        rx_power_dbm=rx_dbm,
        noise_power_dbm=noise_dbm,
        interference_power_dbm=interference_power_dbm,
        sinr_db=measured_sinr_db,
        shannon_capacity_bps=capacity_bps,
        required_sinr_db=required_sinr_db,
        link_margin_db=margin_db,
        available=margin_db >= 0.0,
    )
