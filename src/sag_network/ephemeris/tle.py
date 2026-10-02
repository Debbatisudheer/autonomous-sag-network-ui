from __future__ import annotations

from datetime import datetime, timedelta, UTC

from sag_network.domain.space import OrbitalElements
from sag_network.ephemeris.models import TLERecord


def _checksum(line: str) -> int:
    if len(line) != 69:
        raise ValueError("TLE line must contain exactly 69 characters")
    total = 0
    for character in line[:68]:
        if character.isdigit():
            total += int(character)
        elif character == "-":
            total += 1
    return total % 10


def validate_tle_checksum(line: str) -> None:
    """Validate the checksum digit on one TLE line."""
    if line[68] not in "0123456789":
        raise ValueError("TLE checksum digit is missing")
    expected = int(line[68])
    actual = _checksum(line)
    if actual != expected:
        raise ValueError(f"invalid TLE checksum: expected {expected}, calculated {actual}")


def parse_tle_text(text: str, *, source: str, satellite_name: str | None = None) -> TLERecord:
    """Parse a 2LE/3LE text payload and validate both line checksums."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if len(lines) == 2:
        line1, line2 = lines
        name = satellite_name or line1[2:7].strip()
    elif len(lines) == 3:
        name, line1, line2 = lines
    else:
        raise ValueError("TLE payload must contain two or three non-empty lines")

    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError("invalid TLE line prefixes")
    if line1[2:7] != line2[2:7]:
        raise ValueError("TLE line 1 and line 2 satellite numbers do not match")

    validate_tle_checksum(line1)
    validate_tle_checksum(line2)
    return TLERecord(satellite_name=name.strip(), line1=line1, line2=line2, source=source)


def tle_epoch_utc(record: TLERecord) -> datetime:
    """Convert the TLE epoch fields into an aware UTC datetime."""
    day = int(record.epoch_day_of_year)
    fractional_day = record.epoch_day_of_year - day
    return datetime(record.epoch_year, 1, 1, tzinfo=UTC) + timedelta(
        days=day - 1, seconds=fractional_day * 86_400.0
    )


def tle_to_orbital_elements(record: TLERecord) -> OrbitalElements:
    """Convert TLE mean elements to the existing analytical reference model."""
    inclination_deg = float(record.line2[8:16])
    raan_deg = float(record.line2[17:25])
    eccentricity = float(f"0.{record.line2[26:33]}")
    argument_of_perigee_deg = float(record.line2[34:42])
    mean_anomaly_deg = float(record.line2[43:51])
    mean_motion_rev_day = float(record.line2[52:63])

    from sag_network.space.orbit import EARTH_MU_M3_S2

    mean_motion_rad_s = mean_motion_rev_day * 2.0 * 3.141592653589793 / 86_400.0
    semi_major_axis_m = (EARTH_MU_M3_S2 / mean_motion_rad_s**2) ** (1.0 / 3.0)
    return OrbitalElements(
        semi_major_axis_m=semi_major_axis_m,
        eccentricity=eccentricity,
        inclination_deg=inclination_deg,
        raan_deg=raan_deg,
        argument_of_perigee_deg=argument_of_perigee_deg,
        mean_anomaly_deg=mean_anomaly_deg,
    )
