import math

from sag_network.domain.link import PropagationLosses
from sag_network.physics.link_budget import link_budget, shannon_capacity_bps


def _zero_losses() -> PropagationLosses:
    return PropagationLosses(
        atmospheric_db=0,
        rain_db=0,
        polarization_db=0,
        implementation_db=0,
    )


def test_explicit_additional_losses_reduce_received_power() -> None:
    base = link_budget(
        distance_m=1_000_000,
        frequency_hz=2e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30,
        tx_gain_dbi=20,
        rx_gain_dbi=5,
        noise_figure_db=5,
        propagation_losses=_zero_losses(),
        required_sinr_db=5,
    )
    degraded = link_budget(
        distance_m=1_000_000,
        frequency_hz=2e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30,
        tx_gain_dbi=20,
        rx_gain_dbi=5,
        noise_figure_db=5,
        propagation_losses=PropagationLosses(
            atmospheric_db=2, rain_db=3, polarization_db=1, implementation_db=4
        ),
        required_sinr_db=5,
    )
    assert math.isclose(base.rx_power_dbm - degraded.rx_power_dbm, 10.0, abs_tol=1e-9)
    assert math.isclose(base.sinr_db - degraded.sinr_db, 10.0, abs_tol=1e-9)


def test_shannon_capacity_is_monotonic_in_sinr() -> None:
    low = shannon_capacity_bps(20e6, 0.0)
    high = shannon_capacity_bps(20e6, 10.0)
    assert high > low > 0


def test_interference_reduces_sinr() -> None:
    clean = link_budget(
        distance_m=1_000_000,
        frequency_hz=2e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30,
        tx_gain_dbi=20,
        rx_gain_dbi=5,
        noise_figure_db=5,
        propagation_losses=_zero_losses(),
        required_sinr_db=5,
    )
    interfered = link_budget(
        distance_m=1_000_000,
        frequency_hz=2e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30,
        tx_gain_dbi=20,
        rx_gain_dbi=5,
        noise_figure_db=5,
        propagation_losses=_zero_losses(),
        interference_power_dbm=-85,
        required_sinr_db=5,
    )
    assert interfered.sinr_db < clean.sinr_db
