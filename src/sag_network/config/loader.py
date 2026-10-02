from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sag_network.domain.models import EnvironmentConfig, SimulationConfig


def load_config(path: str | Path) -> tuple[SimulationConfig, EnvironmentConfig]:
    """Load and validate the simulation/environment YAML configuration."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}

    simulation = SimulationConfig.model_validate(raw.get("simulation", {}))
    environment = EnvironmentConfig.model_validate(raw.get("environment", {}))
    return simulation, environment
