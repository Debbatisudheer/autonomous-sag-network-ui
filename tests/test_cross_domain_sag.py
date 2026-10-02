from __future__ import annotations

from sag_network.cross_domain_sag import (
    CrossDomainSAGConfig,
    CrossDomainSAGEvidence,
    CrossDomainSAGIntegrationEngine,
    default_cross_domain_users,
)
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def _records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"cd-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="cross-domain-test",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=5.0 + index,
            unit="ms",
        )
        for index in range(8)
    ]


def _config() -> CrossDomainSAGConfig:
    return CrossDomainSAGConfig(
        reference_time_s=7.0,
        user_demand_bps={
            "sag-user-01": 10e6,
            "sag-user-02": 10e6,
            "sag-user-03": 10e6,
        },
        timeout_s=1.0,
    )


def test_common_user_population_is_shared_across_domains() -> None:
    users = default_cross_domain_users()
    assert [user.user_id for user in users] == [
        "sag-user-01",
        "sag-user-02",
        "sag-user-03",
    ]
    positions = [
        (user.initial_position.latitude_deg, user.initial_position.longitude_deg)
        for user in users
    ]
    assert len(set(positions)) == 3


def test_cross_domain_integration_passes() -> None:
    report = CrossDomainSAGIntegrationEngine().run(
        _records(),
        config=_config(),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.status == "pass"
    assert report.summary.total_user_count == 3
    assert report.summary.total_candidate_count == 15
    assert report.summary.ground_candidate_count == 6
    assert report.summary.air_candidate_count == 6
    assert report.summary.space_candidate_count == 3
    assert len(report.unified_snapshot.associations) == 3


def test_cross_domain_integration_is_deterministic() -> None:
    engine = CrossDomainSAGIntegrationEngine()
    first = engine.run(
        _records(),
        config=_config(),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    second = engine.run(
        _records(),
        config=_config(),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    assert first.integration_fingerprint == second.integration_fingerprint


def test_all_domains_are_represented_in_candidate_state() -> None:
    report = CrossDomainSAGIntegrationEngine().run(
        _records(),
        config=_config(),
        evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE,
    )
    domains = {
        candidate.domain
        for association in report.unified_snapshot.associations
        for candidate in association.candidates
    }
    assert domains == {NetworkDomain.GROUND, NetworkDomain.AIR, NetworkDomain.SPACE}


def test_negative_reference_time_rejected() -> None:
    try:
        CrossDomainSAGConfig(reference_time_s=-1.0, timeout_s=1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("negative reference time must be rejected")


def test_negative_user_demand_rejected() -> None:
    try:
        CrossDomainSAGConfig(
            reference_time_s=0.0,
            timeout_s=1.0,
            user_demand_bps={"sag-user-01": -1.0},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("negative demand must be rejected")
