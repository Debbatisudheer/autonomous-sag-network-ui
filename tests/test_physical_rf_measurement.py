from __future__ import annotations

import math

from sag_network.physical_rf import (
    PhysicalRfEvidence,
    PhysicalRfMeasurementConfig,
    PhysicalRfMeasurementEngine,
)
from sag_network.physical_sdr import (
    PhysicalSdrConfig,
    PhysicalSdrSource,
    SyntheticPhysicalSdrBackend,
)


def capture():
    config = PhysicalSdrConfig(
        channel=0,
        sample_rate_hz=2_000_000.0,
        center_frequency_hz=915_000_000.0,
        sample_count=512,
        timeout_us=100_000,
    )
    source = PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=6800))
    return source, source.capture(config, timestamp_s=68.0)


def test_rf_measurement_is_deterministic() -> None:
    source_a, capture_a = capture()
    source_b, capture_b = capture()
    engine = PhysicalRfMeasurementEngine()
    first = engine.measure(
        capture=capture_a,
        evidence_class=PhysicalRfEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=source_a.external_hardware_used,
    )
    second = engine.measure(
        capture=capture_b,
        evidence_class=PhysicalRfEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=source_b.external_hardware_used,
    )
    assert first == second
    assert first.mean_power_normalized > 0.0
    assert first.peak_amplitude >= first.rms_amplitude > 0.0
    assert first.network_mutation is False


def test_signal_power_is_not_greater_than_total_power() -> None:
    _, capture_data = capture()
    report = PhysicalRfMeasurementEngine().measure(
        capture=capture_data,
        evidence_class=PhysicalRfEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=False,
    )
    assert 0.0 <= report.signal_power_normalized <= report.mean_power_normalized
    assert report.noise_power_normalized > 0.0


def test_snr_is_finite_for_nonzero_synthetic_signal() -> None:
    _, capture_data = capture()
    report = PhysicalRfMeasurementEngine().measure(
        capture=capture_data,
        evidence_class=PhysicalRfEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=False,
    )
    assert math.isfinite(report.snr_db_estimate)
    assert math.isfinite(report.dynamic_range_db)


def test_noise_fraction_changes_noise_estimate_deterministically() -> None:
    _, capture_data = capture()
    engine = PhysicalRfMeasurementEngine()
    low = engine.measure(
        capture=capture_data,
        evidence_class=PhysicalRfEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=False,
        config=PhysicalRfMeasurementConfig(
            noise_floor_fraction=0.10,
            min_noise_power=1e-12,
        ),
    )
    high = engine.measure(
        capture=capture_data,
        evidence_class=PhysicalRfEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=False,
        config=PhysicalRfMeasurementConfig(
            noise_floor_fraction=0.50,
            min_noise_power=1e-12,
        ),
    )
    assert low.noise_power_normalized <= high.noise_power_normalized
    assert low.measurement_fingerprint != high.measurement_fingerprint
