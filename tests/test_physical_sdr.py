from __future__ import annotations

import pytest

from sag_network.physical_sdr import (
    PhysicalSdrConfig,
    PhysicalSdrEvidence,
    PhysicalSdrIntegrationEngine,
    PhysicalSdrSource,
    SyntheticPhysicalSdrBackend,
)
from sag_network.physical_sdr.source import SoapySdrRxBackend


def config() -> PhysicalSdrConfig:
    return PhysicalSdrConfig(
        channel=0,
        sample_rate_hz=2_000_000.0,
        center_frequency_hz=915_000_000.0,
        sample_count=128,
        timeout_us=100_000,
    )


def test_synthetic_physical_sdr_capture_is_deterministic() -> None:
    engine = PhysicalSdrIntegrationEngine()
    first = engine.process(
        source=PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6700)),
        config=config(),
        timestamp_s=67.0,
        evidence_class=PhysicalSdrEvidence.SYNTHETIC_FIXTURE,
    )
    second = engine.process(
        source=PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6700)),
        config=config(),
        timestamp_s=67.0,
        evidence_class=PhysicalSdrEvidence.SYNTHETIC_FIXTURE,
    )
    assert first == second
    assert first.sample_count == 128
    assert first.external_hardware_used is False
    assert first.network_mutation is False


def test_synthetic_capture_has_nonzero_power() -> None:
    report = PhysicalSdrIntegrationEngine().process(
        source=PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6700)),
        config=config(),
        timestamp_s=67.0,
        evidence_class=PhysicalSdrEvidence.SYNTHETIC_FIXTURE,
    )
    assert report.mean_power > 0.0
    assert report.sample_fingerprint != report.processing_fingerprint


def test_different_seed_changes_sample_fingerprint() -> None:
    engine = PhysicalSdrIntegrationEngine()
    first = engine.process(
        source=PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6700)),
        config=config(),
        timestamp_s=67.0,
        evidence_class=PhysicalSdrEvidence.SYNTHETIC_FIXTURE,
    )
    second = engine.process(
        source=PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6701)),
        config=config(),
        timestamp_s=67.0,
        evidence_class=PhysicalSdrEvidence.SYNTHETIC_FIXTURE,
    )
    assert first.sample_fingerprint != second.sample_fingerprint


def test_optional_hardware_backend_has_clear_dependency_error() -> None:
    try:
        import importlib.util

        available = importlib.util.find_spec("SoapySDR") is not None
    except ValueError:
        available = False
    if available:
        pytest.skip("SoapySDR is installed; dependency-error branch is not applicable")
    with pytest.raises(RuntimeError, match="SoapySDR and numpy"):
        SoapySdrRxBackend()


def test_config_rejects_invalid_sample_count() -> None:
    with pytest.raises(ValueError):
        PhysicalSdrConfig(
            channel=0,
            sample_rate_hz=2_000_000.0,
            center_frequency_hz=915_000_000.0,
            sample_count=0,
            timeout_us=100_000,
        )
