from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, UTC
from importlib import import_module
from typing import Any

from sag_network.ephemeris.frames import (
    datetime_to_julian_date_parts,
    teme_to_ecef,
    teme_velocity_to_ecef,
)
from sag_network.ephemeris.models import (
    EphemerisSourceType,
    OMMRecord,
    RealSatelliteState,
    TLERecord,
)
from sag_network.ephemeris.tle import tle_epoch_utc


SatrecFactory = Callable[[str, str], Any]


def _require_sgp4() -> Any:
    try:
        return import_module("sgp4.api")
    except ImportError as exc:
        raise RuntimeError(
            "The Phase 25 real ephemeris backend requires 'sgp4'. "
            "Install the project dependencies with: python -m pip install -e \".[dev]\""
        ) from exc


def satrec_from_tle(record: TLERecord, *, factory: SatrecFactory | None = None) -> Any:
    """Initialize an SGP4 satellite record from TLE lines."""
    if factory is None:
        module = _require_sgp4()
        factory = module.Satrec.twoline2rv
    return factory(record.line1, record.line2)


def satrec_from_omm(record: OMMRecord) -> Any:
    """Initialize an SGP4 satellite record from a normalized OMM record."""
    module = _require_sgp4()
    omm_module = import_module("sgp4.omm")
    satrec = module.Satrec()
    omm_module.initialize(satrec, record.to_sgp4_fields())
    return satrec


def propagate_satrec(
    satrec: Any,
    *,
    satellite_id: str,
    timestamp_utc: datetime,
    source_epoch_utc: datetime,
    source_type: EphemerisSourceType,
) -> RealSatelliteState:
    """Propagate an SGP4 record to an absolute UTC timestamp."""
    if timestamp_utc.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    timestamp = timestamp_utc.astimezone(UTC)
    epoch = source_epoch_utc.astimezone(UTC)
    jd, fraction = datetime_to_julian_date_parts(timestamp)
    error_code, position, velocity = satrec.sgp4(jd, fraction)
    if int(error_code) != 0:
        raise ValueError(f"SGP4 propagation failed with error code {error_code}")

    position_tuple: tuple[float, float, float] = (
        float(position[0]),
        float(position[1]),
        float(position[2]),
    )
    velocity_tuple: tuple[float, float, float] = (
        float(velocity[0]),
        float(velocity[1]),
        float(velocity[2]),
    )
    ecef_position = teme_to_ecef(position_tuple, timestamp)
    ecef_velocity = teme_velocity_to_ecef(position_tuple, velocity_tuple, timestamp)
    return RealSatelliteState(
        satellite_id=satellite_id,
        timestamp_utc=timestamp,
        source_type=source_type,
        source_epoch_utc=epoch,
        elapsed_since_epoch_s=(timestamp - epoch).total_seconds(),
        position_teme_km=position_tuple,
        velocity_teme_km_s=velocity_tuple,
        position_ecef_m=(ecef_position.x_m, ecef_position.y_m, ecef_position.z_m),
        velocity_ecef_m_s=(ecef_velocity.x_m, ecef_velocity.y_m, ecef_velocity.z_m),
    )


class SGP4EphemerisProvider:
    """Absolute-time SGP4 provider backed by a TLE or OMM record."""

    def __init__(
        self,
        *,
        satellite_id: str,
        satrec: Any,
        source_epoch_utc: datetime,
        source_type: EphemerisSourceType,
    ) -> None:
        self.satellite_id = satellite_id
        self.satrec = satrec
        self.source_epoch_utc = source_epoch_utc.astimezone(UTC)
        self.source_type = source_type

    @classmethod
    def from_tle(
        cls,
        record: TLERecord,
        *,
        satellite_id: str | None = None,
        factory: SatrecFactory | None = None,
    ) -> SGP4EphemerisProvider:
        return cls(
            satellite_id=satellite_id or str(record.norad_catalog_id),
            satrec=satrec_from_tle(record, factory=factory),
            source_epoch_utc=tle_epoch_utc(record),
            source_type=EphemerisSourceType.TLE,
        )

    @classmethod
    def from_omm(
        cls, record: OMMRecord, *, satellite_id: str | None = None
    ) -> SGP4EphemerisProvider:
        if record.norad_cat_id is None and satellite_id is None:
            raise ValueError("OMM record requires NORAD_CAT_ID or explicit satellite_id")
        epoch = datetime.fromisoformat(record.epoch)
        if epoch.tzinfo is None:
            raise ValueError("OMM epoch must be timezone-aware")
        epoch = epoch.astimezone(UTC)
        return cls(
            satellite_id=satellite_id or str(record.norad_cat_id),
            satrec=satrec_from_omm(record),
            source_epoch_utc=epoch,
            source_type=EphemerisSourceType.OMM,
        )

    def state_at(self, timestamp_utc: datetime) -> RealSatelliteState:
        return propagate_satrec(
            self.satrec,
            satellite_id=self.satellite_id,
            timestamp_utc=timestamp_utc,
            source_epoch_utc=self.source_epoch_utc,
            source_type=self.source_type,
        )
