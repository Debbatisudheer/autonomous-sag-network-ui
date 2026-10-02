from __future__ import annotations

import pytest

from sag_network.autonomous_validation import (
    AutonomousSAGValidationEngine,
    AutonomousValidationConfig,
    ValidationStatus,
)
from sag_network.cross_domain_sag import CrossDomainSAGEvidence
from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord


def records() -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            record_id=f"phase79-test-{index}",
            timestamp_s=float(index),
            sequence=index,
            source_id="phase79-test",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=1.0 + index * 0.1,
            unit="ms",
        )
        for index in range(4)
    ]


def config() -> AutonomousValidationConfig:
    return AutonomousValidationConfig(
        timestamps_s=[0.0, 15.0, 60.0, 120.0, 300.0, 600.0, 900.0, 1200.0, 1800.0, 2400.0, 2700.0, 3000.0],
        timeout_s=1.0,
    )


def test_phase79_validation_passes() -> None:
    report = AutonomousSAGValidationEngine().run(
        records(), config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    )
    assert report.status is ValidationStatus.PASS
    assert report.summary.failed_check_count == 0
    assert report.summary.deterministic_repeatability
    assert report.summary.evidence_boundary_clean


def test_phase79_is_deterministic() -> None:
    engine = AutonomousSAGValidationEngine()
    first = engine.run(
        records(), config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    )
    second = engine.run(
        records(), config=config(), evidence_class=CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    )
    assert first.integration_fingerprint == second.integration_fingerprint


def test_phase79_rejects_non_monotonic_timestamps() -> None:
    with pytest.raises(ValueError, match="non-decreasing"):
        AutonomousValidationConfig(timestamps_s=[0.0, 2.0, 1.0], timeout_s=1.0)


def test_phase79_public_data_requires_provenance() -> None:
    engine = AutonomousSAGValidationEngine()
    report = engine.run(
        records(),
        config=config(),
        evidence_class=CrossDomainSAGEvidence.PUBLIC_DATA,
        source_sha256="",
        provenance_verified=False,
    )
    assert report.status is ValidationStatus.FAIL
    assert any(check.check_id == "provenance-boundary" for check in report.checks)
    assert any(
        check.check_id == "provenance-boundary" and check.status is ValidationStatus.FAIL
        for check in report.checks
    )


def test_phase79_udp_loopback_repeatability_is_logical() -> None:
    udp_config = config().model_copy(update={"use_udp_loopback": True})
    engine = AutonomousSAGValidationEngine()
    first = engine.run(
        records(), config=udp_config, evidence_class=CrossDomainSAGEvidence.LOCAL_NETWORK_TEST
    )
    second = engine.run(
        records(), config=udp_config, evidence_class=CrossDomainSAGEvidence.LOCAL_NETWORK_TEST
    )
    assert first.status is ValidationStatus.PASS
    assert first.summary.deterministic_repeatability
    assert second.summary.deterministic_repeatability
