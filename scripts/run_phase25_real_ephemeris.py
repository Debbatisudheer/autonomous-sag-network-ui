# ruff: noqa: I001
from __future__ import annotations

import json
from datetime import UTC, timedelta
from pathlib import Path

from sag_network.ephemeris.frames import julian_date
from sag_network.ephemeris.models import EphemerisSourceType
from sag_network.ephemeris.sgp4 import SGP4EphemerisProvider
from sag_network.ephemeris.tle import parse_tle_text, tle_epoch_utc, tle_to_orbital_elements
from sag_network.space.orbit import propagate_satellite_state


ROOT = Path(__file__).resolve().parents[1]
TLE_PATH = ROOT / "data" / "ephemeris" / "iss-zarya.tle"


def main() -> None:
    text = TLE_PATH.read_text(encoding="utf-8")
    record = parse_tle_text(text, source="CelesTrak ISS fixture")
    epoch = tle_epoch_utc(record).astimezone(UTC)

    output: dict[str, object] = {
        "satellite_name": record.satellite_name,
        "norad_catalog_id": record.norad_catalog_id,
        "source": record.source,
        "tle_epoch_utc": epoch.isoformat(),
        "tle_epoch_julian_date": julian_date(epoch),
        "source_type": EphemerisSourceType.TLE.value,
        "fixture_checksums_valid": True,
        "sgp4": {"status": "not_run"},
    }

    try:
        provider = SGP4EphemerisProvider.from_tle(record, satellite_id=str(record.norad_catalog_id))
    except RuntimeError as exc:
        output["sgp4"] = {
            "status": "dependency_missing",
            "message": str(exc),
        }
        print(json.dumps(output, indent=2))
        return

    real_state = provider.state_at(epoch)
    analytical_elements = tle_to_orbital_elements(record)
    analytical = propagate_satellite_state(analytical_elements, 600.0)
    sgp4_plus_600 = provider.state_at(epoch + timedelta(seconds=600))
    analytical_position = analytical.position_ecef
    real_position = sgp4_plus_600.position_ecef_m
    position_delta_km = (
        (
            (real_position[0] - analytical_position.x_m) ** 2
            + (real_position[1] - analytical_position.y_m) ** 2
            + (real_position[2] - analytical_position.z_m) ** 2
        )
        ** 0.5
        / 1_000.0
    )

    output["sgp4"] = {
        "status": "pass",
        "propagation_model": real_state.propagation_model,
        "reference_frame": real_state.reference_frame,
        "epoch_position_teme_km": list(real_state.position_teme_km),
        "plus_600s_position_ecef_m": list(sgp4_plus_600.position_ecef_m),
        "plus_600s_velocity_ecef_m_s": list(sgp4_plus_600.velocity_ecef_m_s),
        "analytical_reference_position_ecef_m": [
            analytical_position.x_m,
            analytical_position.y_m,
            analytical_position.z_m,
        ],
        "real_vs_analytical_position_delta_km": position_delta_km,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
