from __future__ import annotations

import pytest

from sag_network.physical_sdr.models import PhysicalSdrCapture
from sag_network.physical_wireless_link import (
    PhysicalWirelessEvidence,
    PhysicalWirelessLinkConfig,
    PhysicalWirelessLinkEngine,
)


def config() -> PhysicalWirelessLinkConfig:
    return PhysicalWirelessLinkConfig(
        source_id="ground",
        destination_id="air",
        payload=b"SAG-LINK",
        sample_rate_hz=2_000_000.0,
        symbol_rate_hz=100_000.0,
        amplitude=0.8,
        decision_threshold=0.5,
    )


def test_synthetic_link_delivers_payload() -> None:
    report = PhysicalWirelessLinkEngine().process_synthetic(
        config=config(),
        timestamp_s=69.0,
    )
    assert report.delivered is True
    assert report.crc_valid is True
    assert report.bit_error_rate == 0.0
    assert report.evidence_class is PhysicalWirelessEvidence.SYNTHETIC_FIXTURE
    assert report.network_mutation is False


def test_synthetic_link_is_deterministic() -> None:
    engine = PhysicalWirelessLinkEngine()
    first = engine.process_synthetic(config=config(), timestamp_s=69.0)
    second = engine.process_synthetic(config=config(), timestamp_s=69.0)
    assert first == second


def test_corrupted_sample_fails_crc() -> None:
    engine = PhysicalWirelessLinkEngine()
    frame = engine.build_frame(config())
    i_samples, q_samples = engine.modulate_ook(frame, config())
    samples_per_symbol = config().samples_per_symbol
    bit_index = frame.bit_count - 5
    center = bit_index * samples_per_symbol + samples_per_symbol // 2
    original = i_samples[center]
    replacement = 0.0 if original >= config().amplitude * config().decision_threshold else config().amplitude
    i_samples[center] = replacement
    i_samples[center + 1] = replacement
    capture = PhysicalSdrCapture(
        timestamp_s=69.0,
        sample_rate_hz=config().sample_rate_hz,
        center_frequency_hz=0.0,
        channel=0,
        i_samples=i_samples,
        q_samples=q_samples,
        hardware_device="synthetic-ook-link",
    )
    report = engine.process_capture(
        capture=capture,
        config=config(),
        evidence_class=PhysicalWirelessEvidence.SYNTHETIC_FIXTURE,
        external_hardware_used=False,
    )
    assert report.delivered is False


def test_invalid_symbol_ratio_is_rejected() -> None:
    config = PhysicalWirelessLinkConfig(
        source_id="ground",
        destination_id="air",
        payload=b"x",
        sample_rate_hz=2_000_000.0,
        symbol_rate_hz=150_000.0,
        amplitude=0.8,
        decision_threshold=0.5,
    )

    with pytest.raises(ValueError):
        _ = config.samples_per_symbol
