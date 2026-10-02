from __future__ import annotations

from sag_network.channel.evaluator import apply_channel_to_link, NTNChannelModel
from sag_network.channel.models import NTNChannelContext, NTNChannelResult
from sag_network.domain.link import LinkBudget, PropagationLosses
from sag_network.domain.models import GeoPoint
from sag_network.domain.space import CartesianPoint, GroundSatelliteVisibility
from sag_network.physics.link_budget import link_budget
from sag_network.space.geodesy import geodetic_to_ecef, subtract, vector_norm_m
from sag_network.space.orbit import EARTH_ROTATION_RATE_RAD_S
from sag_network.space.visibility import ground_to_satellite_visibility

C_MPS = 299_792_458.0


def range_rate_mps(
    satellite_position_ecef: CartesianPoint,
    satellite_velocity_ecef: CartesianPoint,
    ground_position: GeoPoint,
) -> float:
    """Relative radial velocity of a ground observer and satellite in ECEF."""
    ground_ecef = geodetic_to_ecef(ground_position)
    relative_position = subtract(satellite_position_ecef, ground_ecef)
    ground_velocity_ecef = CartesianPoint(
        x_m=-EARTH_ROTATION_RATE_RAD_S * ground_ecef.y_m,
        y_m=EARTH_ROTATION_RATE_RAD_S * ground_ecef.x_m,
        z_m=0.0,
    )
    relative_velocity = CartesianPoint(
        x_m=satellite_velocity_ecef.x_m - ground_velocity_ecef.x_m,
        y_m=satellite_velocity_ecef.y_m - ground_velocity_ecef.y_m,
        z_m=satellite_velocity_ecef.z_m - ground_velocity_ecef.z_m,
    )
    slant_range = vector_norm_m(relative_position)
    return (
        relative_position.x_m * relative_velocity.x_m
        + relative_position.y_m * relative_velocity.y_m
        + relative_position.z_m * relative_velocity.z_m
    ) / slant_range


def doppler_shift_hz(carrier_frequency_hz: float, range_rate_mps: float) -> float:
    """Non-relativistic first-order Doppler shift; positive means observed upshift for approach."""
    if carrier_frequency_hz <= 0:
        raise ValueError("carrier_frequency_hz must be positive")
    return -carrier_frequency_hz * range_rate_mps / C_MPS


def propagation_delay_ms(slant_range_m: float) -> float:
    """One-way free-space propagation delay from slant range."""
    if slant_range_m <= 0:
        raise ValueError("slant_range_m must be positive")
    return slant_range_m / C_MPS * 1_000.0


def satellite_link_state(
    *,
    timestamp_s: float,
    ground_station_id: str,
    ground_position: GeoPoint,
    satellite_position_ecef: CartesianPoint,
    satellite_velocity_ecef: CartesianPoint,
    carrier_frequency_hz: float,
    bandwidth_hz: float,
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    noise_figure_db: float,
    propagation_losses: PropagationLosses,
    interference_power_dbm: float | None = None,
    required_sinr_db: float = 0.0,
    minimum_elevation_deg: float = 10.0,
    channel_model: NTNChannelModel | None = None,
    channel_link_id: str | None = None,
) -> dict[str, float | bool | str]:
    """Produce a physically derived ground-to-satellite NTN link state."""
    visibility: GroundSatelliteVisibility = ground_to_satellite_visibility(
        timestamp_s=timestamp_s,
        ground_station_id=ground_station_id,
        ground_position=ground_position,
        satellite_position_ecef=satellite_position_ecef,
        minimum_elevation_deg=minimum_elevation_deg,
    )
    rate = range_rate_mps(
        satellite_position_ecef=satellite_position_ecef,
        satellite_velocity_ecef=satellite_velocity_ecef,
        ground_position=ground_position,
    )
    budget: LinkBudget = link_budget(
        distance_m=visibility.slant_range_m,
        frequency_hz=carrier_frequency_hz,
        bandwidth_hz=bandwidth_hz,
        tx_power_dbm=tx_power_dbm,
        tx_gain_dbi=tx_gain_dbi,
        rx_gain_dbi=rx_gain_dbi,
        noise_figure_db=noise_figure_db,
        propagation_losses=propagation_losses,
        interference_power_dbm=interference_power_dbm,
        required_sinr_db=required_sinr_db,
    )
    channel_result: NTNChannelResult | None = None
    if channel_model is not None:
        channel_result = channel_model.evaluate(
            NTNChannelContext(
                link_id=channel_link_id or ground_station_id,
                timestamp_s=timestamp_s,
                elevation_deg=visibility.elevation_deg,
                slant_range_m=visibility.slant_range_m,
                frequency_hz=carrier_frequency_hz,
                bandwidth_hz=bandwidth_hz,
                relative_speed_mps=abs(rate),
            )
        )
        budget = apply_channel_to_link(link=budget, result=channel_result)
    available = visibility.visible and budget.available
    return {
        "timestamp_s": timestamp_s,
        "ground_station_id": ground_station_id,
        "elevation_deg": visibility.elevation_deg,
        "slant_range_m": visibility.slant_range_m,
        "visible": visibility.visible,
        "range_rate_mps": rate,
        "doppler_shift_hz": doppler_shift_hz(carrier_frequency_hz, rate),
        "propagation_delay_ms": propagation_delay_ms(visibility.slant_range_m),
        "rx_power_dbm": budget.rx_power_dbm,
        "noise_power_dbm": budget.noise_power_dbm,
        "sinr_db": budget.sinr_db,
        "link_margin_db": budget.link_margin_db,
        "shannon_capacity_bps": budget.shannon_capacity_bps,
        "available": available,
        **({
            "channel_condition": channel_result.condition.value,
            "los_probability": channel_result.los_probability,
            "shadow_fading_db": channel_result.shadow_fading_db,
            "clutter_loss_db": channel_result.clutter_loss_db,
            "small_scale_fading_gain_db": channel_result.small_scale_fading_gain_db,
            "maximum_doppler_hz": channel_result.maximum_doppler_hz,
        } if channel_result is not None else {}),
    }
