from sag_network.physics.link_budget import (
    free_space_path_loss_db,
    sinr_db,
    thermal_noise_power_dbm,
)


def test_fspl_matches_known_reference():
    result = free_space_path_loss_db(1_000.0, 2_000_000_000.0)
    assert 98.4 < result < 98.6


def test_noise_floor_for_20_mhz():
    result = thermal_noise_power_dbm(20_000_000, 5)
    assert -96.1 < result < -95.8


def test_sinr_without_interference():
    result = sinr_db(-70, -100)
    assert 29.9 < result < 30.1
