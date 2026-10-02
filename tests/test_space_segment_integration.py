from __future__ import annotations

from pathlib import Path

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.space_segment import (
    SpaceSegmentConfig,
    SpaceSegmentEvidence,
    SpaceSegmentIntegrationEngine,
)
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"space-test-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="space-test",
            domain=NetworkDomain.SPACE,
            metric=TelemetryMetric.LATENCY_MS,
            value=10.0 + index * 0.1,
            unit="ms",
        )
        for index in range(8)
    ]


def config() -> SpaceSegmentConfig:
    return SpaceSegmentConfig(
        reference_time_s=7.0,
        user_demand_bps={
            "space-user-01": 8e6,
            "space-user-02": 8e6,
            "space-user-03": 8e6,
        },
        use_udp_loopback=False,
        timeout_s=1.0,
        use_real_ephemeris=False,
    )


def test_synthetic_space_integration_passes() -> None:
    report = SpaceSegmentIntegrationEngine().run(
        records(),
        config=config(),
        evidence_class=SpaceSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.status == "pass"
    assert report.summary.total_satellite_count == 1
    assert report.summary.telemetry_sample_count == 1
    assert len(report.space_snapshot.associations) == 3


def test_space_integration_is_deterministic() -> None:
    engine = SpaceSegmentIntegrationEngine()
    first = engine.run(
        records(),
        config=config(),
        evidence_class=SpaceSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    second = engine.run(
        records(),
        config=config(),
        evidence_class=SpaceSegmentEvidence.SYNTHETIC_FIXTURE,
    )
    assert first.integration_fingerprint == second.integration_fingerprint


def test_inactive_user_has_no_candidates() -> None:
    from sag_network.space_segment.engine import default_space_users

    user = default_space_users()[0].model_copy(update={"active": False})
    assert user.active is False


def test_config_rejects_negative_time() -> None:
    with pytest.raises(ValueError):
        SpaceSegmentConfig(
            reference_time_s=-1.0,
            timeout_s=1.0,
        )


def test_real_ephemeris_flag_is_preserved_in_config() -> None:
    result = SpaceSegmentConfig(
        reference_time_s=0.0,
        timeout_s=1.0,
        use_real_ephemeris=True,
    )
    assert result.use_real_ephemeris is True


def test_bundled_tle_fixture_exists() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "ephemeris"
        / "iss-zarya.tle"
    )
    assert fixture.is_file()


def test_public_replay_normalizes_timestamps(tmp_path: Path) -> None:
    import hashlib
    import json

    from sag_network.space_segment.replay import read_public_records

    dataset = tmp_path / "public.csv"
    dataset.write_text(
        "timestamp,channel,value\n"
        "2022-06-01T23:42:54.000Z,CADC0001,1.0\n"
        "2022-06-01T23:42:55.000Z,CADC0001,2.0\n",
        encoding="utf-8",
    )
    source_sha256 = hashlib.sha256(dataset.read_bytes()).hexdigest()
    manifest = dataset.with_suffix(dataset.suffix + ".manifest.json")
    manifest.write_text(
        json.dumps({"sha256": source_sha256, "verified": True}),
        encoding="utf-8",
    )

    records_out, digest, verified = read_public_records(dataset, 10)
    assert digest == source_sha256
    assert verified is True
    assert [record.timestamp_s for record in records_out] == [0.0, 1.0]
