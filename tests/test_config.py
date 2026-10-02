from sag_network.config.loader import load_config


def test_dev_config_loads():
    simulation, environment = load_config("configs/dev.yaml")
    assert simulation.seed == 42
    assert simulation.step_seconds == 1
    assert environment.frequency_hz == 3.5e9
    assert environment.bandwidth_hz == 20e6
