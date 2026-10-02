from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

import pytest
from pydantic import ValidationError

from sag_network.domain.models import GeoPoint
from sag_network.domain.space import OrbitalElements
from sag_network.ephemeris.celestrak import CelesTrakClient
from sag_network.ephemeris.frames import (
    datetime_to_julian_date_parts,
    gmst_degrees,
    julian_date,
    teme_to_ecef,
    teme_velocity_to_ecef,
)
from sag_network.ephemeris.models import (
    EphemerisSimulationConfig,
    EphemerisSourceType,
    OMMRecord,
    RealSatelliteDefinition,
)
from sag_network.ephemeris.omm import parse_omm_csv, parse_omm_json
from sag_network.ephemeris.reference import SimulationEphemerisAdapter
from sag_network.ephemeris.sgp4 import propagate_satrec, SGP4EphemerisProvider
from sag_network.ephemeris.tle import parse_tle_text, tle_epoch_utc, tle_to_orbital_elements


TLE = (
    "ISS (ZARYA)\n"
    "1 25544U 98067A   26271.46476993  .00006013  00000+0  11848-3 0  9990\n"
    "2 25544  51.6312 148.9632 0007159 198.2260 161.8473 15.48680135587767\n"
)


def test_parse_real_fixture() -> None:
    record = parse_tle_text(TLE, source="celestrak-fixture")
    assert record.satellite_name == "ISS (ZARYA)"
    assert record.norad_catalog_id == 25544
    assert record.epoch_year == 2026
    assert record.epoch_day_of_year == pytest.approx(271.46476993)
    assert tle_epoch_utc(record).tzinfo is not None


def test_bad_checksum_rejected() -> None:
    bad = TLE.replace("9990", "9991")
    with pytest.raises(ValueError, match="checksum"):
        parse_tle_text(bad, source="fixture")


def test_tle_to_analytical_reference_elements() -> None:
    record = parse_tle_text(TLE, source="fixture")
    elements = tle_to_orbital_elements(record)
    assert isinstance(elements, OrbitalElements)
    assert elements.eccentricity == pytest.approx(0.0007159)
    assert elements.inclination_deg == pytest.approx(51.6312)
    assert elements.semi_major_axis_m > 6_378_137.0


def test_julian_date_j2000() -> None:
    timestamp = datetime(2000, 1, 1, 12, tzinfo=UTC)
    whole, fraction = datetime_to_julian_date_parts(timestamp)
    assert whole == 2_451_545.0
    assert fraction == pytest.approx(0.0)
    assert julian_date(timestamp) == pytest.approx(2_451_545.0)
    assert gmst_degrees(timestamp) == pytest.approx(280.46061837, abs=1e-7)


def test_julian_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        julian_date(datetime.fromisoformat("2026-01-01T00:00:00"))


def test_teme_to_ecef_rotates_and_scales() -> None:
    result = teme_to_ecef((7_000.0, 0.0, 0.0), datetime(2026, 1, 1, tzinfo=UTC))
    norm = (result.x_m**2 + result.y_m**2 + result.z_m**2) ** 0.5
    assert norm == pytest.approx(7_000_000.0)


def test_teme_velocity_rotation_is_physical_scale() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    velocity = teme_velocity_to_ecef((7_000.0, 0.0, 0.0), (0.0, 7.5, 0.0), timestamp)
    speed = (velocity.x_m**2 + velocity.y_m**2 + velocity.z_m**2) ** 0.5
    assert 6_900.0 < speed < 8_000.0


def test_omm_json_parser() -> None:
    payload = (
        '{"OBJECT_NAME":"ISS (ZARYA)","NORAD_CAT_ID":25544,'
        '"EPOCH":"2026-09-28T11:09:16.122Z","MEAN_MOTION":15.48680135,'
        '"ECCENTRICITY":0.0007159,"INCLINATION":51.6312,'
        '"RA_OF_ASC_NODE":148.9632,"ARG_OF_PERICENTER":198.2260,'
        '"MEAN_ANOMALY":161.8473}'
    )
    records = parse_omm_json(payload)
    assert len(records) == 1
    assert records[0].norad_cat_id == 25544
    assert records[0].to_sgp4_fields()["MEAN_ELEMENT_THEORY"] == "SGP4"


def test_omm_csv_parser() -> None:
    payload = (
        "OBJECT_NAME,NORAD_CAT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,"
        "RA_OF_ASC_NODE,ARG_OF_PERICENTER,MEAN_ANOMALY\n"
        "ISS (ZARYA),25544,2026-09-28T11:09:16.122Z,15.48680135,0.0007159,51.6312,"
        "148.9632,198.2260,161.8473\n"
    )
    records = parse_omm_csv(payload)
    assert len(records) == 1
    assert records[0].mean_motion == pytest.approx(15.48680135)


def test_celestrak_url_builder() -> None:
    client = CelesTrakClient()
    assert client.build_url(catalog_number=25544, format_name="TLE") == (
        "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"
    )


def test_sgp4_provider_with_fake_backend() -> None:
    record = parse_tle_text(TLE, source="fixture")

    class FakeSatrec:
        def sgp4(
            self, _jd: float, _fraction: float
        ) -> tuple[int, tuple[float, float, float], tuple[float, float, float]]:
            return 0, (7000.0, 0.0, 100.0), (0.0, 7.5, 0.0)

    provider = SGP4EphemerisProvider.from_tle(
        record,
        satellite_id="iss-25544",
        factory=lambda _line1, _line2: FakeSatrec(),
    )
    state = provider.state_at(datetime(2026, 9, 28, tzinfo=UTC))
    assert state.satellite_id == "iss-25544"
    assert state.source_type is EphemerisSourceType.TLE
    assert state.position_teme_km == (7000.0, 0.0, 100.0)
    assert state.sgp4_error_code == 0


def test_sgp4_propagation_error_is_rejected() -> None:
    timestamp = datetime(2026, 9, 28, tzinfo=UTC)

    class ErrorSatrec:
        def sgp4(
            self, _jd: float, _fraction: float
        ) -> tuple[int, tuple[float, float, float], tuple[float, float, float]]:
            return 6, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="error code 6"):
        propagate_satrec(
            ErrorSatrec(),
            satellite_id="x",
            timestamp_utc=timestamp,
            source_epoch_utc=timestamp,
            source_type=EphemerisSourceType.TLE,
        )


def test_simulation_adapter_maps_relative_clock() -> None:
    timestamp = datetime(2026, 9, 28, tzinfo=UTC)

    class StubProvider:
        def state_at(self, when: datetime):
            from sag_network.ephemeris.models import RealSatelliteState

            return RealSatelliteState(
                satellite_id=when.isoformat(),
                timestamp_utc=when,
                source_type=EphemerisSourceType.TLE,
                source_epoch_utc=when,
                elapsed_since_epoch_s=0.0,
                position_teme_km=(7000.0, 0.0, 0.0),
                velocity_teme_km_s=(0.0, 7.5, 0.0),
                position_ecef_m=(7000000.0, 0.0, 0.0),
                velocity_ecef_m_s=(0.0, 7500.0, 0.0),
            )

    adapter = SimulationEphemerisAdapter(
        StubProvider(),
        EphemerisSimulationConfig(simulation_epoch_utc=timestamp),
    )
    result = adapter.state_at(600.0)
    assert result.timestamp_utc == datetime(2026, 9, 28, 0, 10, tzinfo=UTC)


def test_real_satellite_definition_validation() -> None:
    model = RealSatelliteDefinition(
        satellite_id="iss-25544",
        source_type=EphemerisSourceType.TLE,
    )
    assert model.active is True


def test_omm_validation_requires_positive_mean_motion() -> None:
    with pytest.raises(ValidationError):
        OMMRecord(
            OBJECT_NAME="X",
            EPOCH="2026-09-28T00:00:00Z",
            MEAN_MOTION=0.0,
            ECCENTRICITY=0.1,
            INCLINATION=10.0,
            RA_OF_ASC_NODE=20.0,
            ARG_OF_PERICENTER=30.0,
            MEAN_ANOMALY=40.0,
        )


def test_real_ephemeris_constellation_reuses_satellite_candidate_contract() -> None:
    from sag_network.domain.link import PropagationLosses
    from sag_network.domain.mobility import MobileUser, MobilityProfile
    from sag_network.ephemeris.models import RealSatelliteState
    from sag_network.space.real_connectivity import (
        RealEphemerisConstellation,
        user_real_satellite_candidates,
    )

    class StubProvider:
        def state_at(self, timestamp_s: float) -> RealSatelliteState:
            return RealSatelliteState(
                satellite_id="iss-25544",
                timestamp_utc=datetime(2026, 9, 28, tzinfo=UTC),
                source_type=EphemerisSourceType.TLE,
                source_epoch_utc=datetime(2026, 9, 28, tzinfo=UTC),
                elapsed_since_epoch_s=timestamp_s,
                position_teme_km=(7000.0, 0.0, 0.0),
                velocity_teme_km_s=(0.0, 7.5, 0.0),
                position_ecef_m=(7000000.0, 0.0, 0.0),
                velocity_ecef_m_s=(0.0, 7500.0, 0.0),
            )

    user = MobileUser(
        user_id="user-01",
        initial_position=GeoPoint(latitude_deg=0.0, longitude_deg=0.0, altitude_m=0.0),
        mobility=MobilityProfile(),
    )
    definition = RealSatelliteDefinition(
        satellite_id="iss-25544",
        source_type=EphemerisSourceType.TLE,
        minimum_elevation_deg=0.0,
    )
    constellation = RealEphemerisConstellation([(definition, StubProvider())])
    candidates = user_real_satellite_candidates(
        constellation=constellation,
        user=user,
        timestamp_s=0.0,
        carrier_frequency_hz=2.2e9,
        bandwidth_hz=10e6,
        tx_power_dbm=30.0,
        tx_gain_dbi=0.0,
        rx_gain_dbi=0.0,
        noise_figure_db=5.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=0.0,
            rain_db=0.0,
            polarization_db=0.0,
            implementation_db=0.0,
        ),
        required_sinr_db=-10.0,
    )
    assert len(candidates) == 1
    assert candidates[0].satellite_id == "iss-25544"


def test_sgp4_fixture_source_is_real_celestrak_path() -> None:
    fixture = Path(__file__).resolve().parents[1] / "data" / "ephemeris" / "iss-zarya.tle"
    record = parse_tle_text(
        fixture.read_text(encoding="utf-8"),
        source="https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
    )
    assert record.norad_catalog_id == 25544
    assert "celestrak.org" in record.source
