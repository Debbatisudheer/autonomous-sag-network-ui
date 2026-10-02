from __future__ import annotations

import json
import math
from datetime import UTC
from pathlib import Path

from sag_network.channel.evaluator import NTNChannelModel, channel_fingerprint
from sag_network.channel.models import NTNChannelConfig, NTNChannelContext, NTNEnvironment, WeatherAttenuation
from sag_network.domain.link import PropagationLosses
from sag_network.domain.models import GeoPoint
from sag_network.domain.space import CartesianPoint
from sag_network.ephemeris.reference import EphemerisSimulationConfig, SimulationEphemerisAdapter
from sag_network.ephemeris.sgp4 import SGP4EphemerisProvider
from sag_network.ephemeris.tle import parse_tle_text, tle_epoch_utc
from sag_network.space.link import satellite_link_state

ROOT = Path(__file__).resolve().parents[1]
TLE_PATH = ROOT / "data" / "ephemeris" / "iss-zarya.tle"


def _nadir_ground_point(position_ecef_m: tuple[float, float, float]) -> GeoPoint:
    """Project a real satellite ECEF position to a deterministic ground reference point."""
    x_m, y_m, z_m = position_ecef_m
    longitude_deg = math.degrees(math.atan2(y_m, x_m))
    latitude_deg = math.degrees(math.atan2(z_m, math.hypot(x_m, y_m)))
    return GeoPoint(latitude_deg=latitude_deg, longitude_deg=longitude_deg, altitude_m=0.0)


def main() -> None:
    tle_text = TLE_PATH.read_text(encoding="utf-8")
    tle = parse_tle_text(tle_text, source="CelesTrak ISS fixture")
    epoch_utc = tle_epoch_utc(tle).astimezone(UTC)
    try:
        provider = SGP4EphemerisProvider.from_tle(tle, satellite_id="25544")
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "status": "dependency_missing",
                    "phase": "28",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return

    adapter = SimulationEphemerisAdapter(
        provider,
        EphemerisSimulationConfig(
            simulation_epoch_utc=epoch_utc,
            max_propagation_age_s=7.0 * 86_400.0,
        ),
    )
    state = adapter.state_at(300.0)
    ground = _nadir_ground_point(state.position_ecef_m)
    channel_model = NTNChannelModel(
        NTNChannelConfig(
            seed=42,
            environment=NTNEnvironment.SUBURBAN_RURAL,
            weather=WeatherAttenuation(
                gas_specific_db_per_km=0.005,
                rain_specific_db_per_km=0.002,
                cloud_specific_db_per_km=0.001,
                scintillation_db=0.25,
            ),
        )
    )
    link = satellite_link_state(
        timestamp_s=300.0,
        ground_station_id="hyd-ref",
        ground_position=ground,
        satellite_position_ecef=CartesianPoint(
            x_m=state.position_ecef_m[0],
            y_m=state.position_ecef_m[1],
            z_m=state.position_ecef_m[2],
        ),
        satellite_velocity_ecef=CartesianPoint(
            x_m=state.velocity_ecef_m_s[0],
            y_m=state.velocity_ecef_m_s[1],
            z_m=state.velocity_ecef_m_s[2],
        ),
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
        channel_model=channel_model,
        channel_link_id="hyd-ref:25544",
    )
    if "channel_condition" not in link:
        raise RuntimeError("real SGP4 state is below visibility threshold for the demo epoch")

    print(
        json.dumps(
            {
                "status": "pass",
                "phase": "28",
                "baseline": "Phase 27 real SGP4 ephemeris",
                "satellite_id": "25544",
                "epoch_utc": epoch_utc.isoformat(),
                "sample_simulation_time_s": 300.0,
                "ground_reference": "deterministic nadir projection of the real SGP4 satellite state",
                "ground_latitude_deg": ground.latitude_deg,
                "ground_longitude_deg": ground.longitude_deg,
                "elevation_deg": link["elevation_deg"],
                "slant_range_m": link["slant_range_m"],
                "channel_condition": link["channel_condition"],
                "los_probability": link["los_probability"],
                "shadow_fading_db": link["shadow_fading_db"],
                "clutter_loss_db": link["clutter_loss_db"],
                "small_scale_fading_gain_db": link["small_scale_fading_gain_db"],
                "maximum_doppler_hz": link["maximum_doppler_hz"],
                "rx_power_dbm": link["rx_power_dbm"],
                "sinr_db": link["sinr_db"],
                "shannon_capacity_bps": link["shannon_capacity_bps"],
                "available": link["available"],
                "channel_fingerprint": channel_fingerprint(
                    NTNChannelModel(channel_model.config).evaluate(
                        NTNChannelContext(
                            link_id="hyd-ref:25544",
                            timestamp_s=300.0,
                            elevation_deg=float(link["elevation_deg"]),
                            slant_range_m=float(link["slant_range_m"]),
                            frequency_hz=3.5e9,
                            bandwidth_hz=20e6,
                            relative_speed_mps=abs(float(link["range_rate_mps"])),
                        )
                    )
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
