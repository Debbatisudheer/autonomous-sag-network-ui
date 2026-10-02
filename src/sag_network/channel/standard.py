from __future__ import annotations

import bisect
import math

from sag_network.channel.models import ChannelCondition, NTNBand, NTNEnvironment

_REFERENCE_ELEVATIONS_DEG = (10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0)

_LOS_PROBABILITY = {
    NTNEnvironment.DENSE_URBAN: (0.282, 0.331, 0.398, 0.468, 0.537, 0.612, 0.738, 0.820, 0.981),
    NTNEnvironment.URBAN: (0.246, 0.386, 0.493, 0.613, 0.726, 0.805, 0.919, 0.968, 0.992),
    NTNEnvironment.SUBURBAN_RURAL: (0.782, 0.869, 0.919, 0.929, 0.935, 0.940, 0.949, 0.952, 0.998),
}

# Tables 6.6.2-1 to 6.6.2-3 of 3GPP TR 38.811 V15.2.0.
# Each entry is (LOS sigma, NLOS sigma, NLOS clutter loss).
_SHADOW_CLUTTER: dict[
    NTNEnvironment, dict[NTNBand, tuple[tuple[float, float, float], ...]]
] = {
    NTNEnvironment.DENSE_URBAN: {
        NTNBand.S_BAND: (
            (3.5, 15.5, 34.3),
            (3.4, 13.9, 30.9),
            (2.9, 12.4, 29.0),
            (3.0, 11.7, 27.7),
            (3.1, 10.6, 26.8),
            (2.7, 10.5, 26.2),
            (2.5, 10.1, 25.8),
            (2.3, 9.2, 25.5),
            (1.2, 9.2, 25.5),
        ),
        NTNBand.KA_BAND: (
            (2.9, 17.1, 44.3),
            (2.4, 17.1, 39.9),
            (2.7, 15.6, 37.5),
            (2.4, 14.6, 35.8),
            (2.4, 14.2, 34.6),
            (2.7, 12.6, 33.8),
            (2.6, 12.1, 33.3),
            (2.8, 12.3, 33.0),
            (0.6, 12.3, 32.9),
        ),
    },
    NTNEnvironment.URBAN: {
        NTNBand.S_BAND: tuple((4.0, 6.0, clutter) for clutter in (34.3, 30.9, 29.0, 27.7, 26.8, 26.2, 25.8, 25.5, 25.5)),
        NTNBand.KA_BAND: tuple((4.0, 6.0, clutter) for clutter in (44.3, 39.9, 37.5, 35.8, 34.6, 33.8, 33.3, 33.0, 32.9)),
    },
    NTNEnvironment.SUBURBAN_RURAL: {
        NTNBand.S_BAND: (
            (1.79, 8.93, 19.52),
            (1.14, 9.08, 18.17),
            (1.14, 8.78, 18.42),
            (0.92, 10.25, 18.28),
            (1.42, 10.56, 18.63),
            (1.56, 10.74, 17.68),
            (0.85, 10.17, 16.50),
            (0.72, 11.52, 16.30),
            (0.72, 11.52, 16.30),
        ),
        NTNBand.KA_BAND: (
            (1.9, 10.7, 29.5),
            (1.6, 10.0, 24.6),
            (1.9, 11.2, 21.9),
            (2.3, 11.6, 20.0),
            (2.7, 11.8, 18.7),
            (3.1, 10.8, 17.8),
            (3.0, 10.8, 17.2),
            (3.6, 10.8, 16.9),
            (0.4, 10.8, 16.8),
        ),
    },
}


def select_band(frequency_hz: float) -> NTNBand:
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    return NTNBand.S_BAND if frequency_hz <= 6_000_000_000.0 else NTNBand.KA_BAND


def _nearest_reference_index(elevation_deg: float) -> int:
    if not 0.0 <= elevation_deg <= 90.0:
        raise ValueError("elevation_deg must be between 0 and 90 degrees")
    if elevation_deg <= 10.0:
        return 0
    if elevation_deg >= 90.0:
        return len(_REFERENCE_ELEVATIONS_DEG) - 1
    right = bisect.bisect_left(_REFERENCE_ELEVATIONS_DEG, elevation_deg)
    left = right - 1
    if elevation_deg - _REFERENCE_ELEVATIONS_DEG[left] < _REFERENCE_ELEVATIONS_DEG[right] - elevation_deg:
        return left
    return right


def los_probability(*, elevation_deg: float, environment: NTNEnvironment) -> float:
    """Return 3GPP TR 38.811 LOS probability using the nearest 10-degree reference angle."""
    index = _nearest_reference_index(elevation_deg)
    return _LOS_PROBABILITY[environment][index]


def shadow_and_clutter(
    *,
    elevation_deg: float,
    environment: NTNEnvironment,
    band: NTNBand,
    condition: ChannelCondition,
) -> tuple[float, float]:
    """Return (shadow sigma dB, clutter loss dB) from the 38.811 reference tables."""
    index = _nearest_reference_index(elevation_deg)
    sigma_los, sigma_nlos, clutter_nlos = _SHADOW_CLUTTER[environment][band][index]
    if condition is ChannelCondition.LOS:
        return sigma_los, 0.0
    return sigma_nlos, clutter_nlos


def shadow_plus_clutter_expectation_db(
    *,
    elevation_deg: float,
    environment: NTNEnvironment,
    band: NTNBand,
) -> tuple[float, float, float]:
    """Return LOS probability, shadow sigma, and expected clutter for a probabilistic summary."""
    probability = los_probability(elevation_deg=elevation_deg, environment=environment)
    los_sigma, _ = shadow_and_clutter(
        elevation_deg=elevation_deg,
        environment=environment,
        band=band,
        condition=ChannelCondition.LOS,
    )
    _, nlos_clutter = shadow_and_clutter(
        elevation_deg=elevation_deg,
        environment=environment,
        band=band,
        condition=ChannelCondition.NLOS,
    )
    expected_sigma = probability * los_sigma + (1.0 - probability) * shadow_and_clutter(
        elevation_deg=elevation_deg,
        environment=environment,
        band=band,
        condition=ChannelCondition.NLOS,
    )[0]
    return probability, expected_sigma, (1.0 - probability) * nlos_clutter


def slant_airmass_factor(elevation_deg: float) -> float:
    """Simple geometric slant-air-mass factor for supplied per-km weather inputs."""
    if not 0.0 < elevation_deg <= 90.0:
        raise ValueError("elevation_deg must be greater than 0 and at most 90 degrees")
    return 1.0 / max(math.sin(math.radians(elevation_deg)), 0.1)
