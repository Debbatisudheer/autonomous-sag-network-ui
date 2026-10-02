from __future__ import annotations

from pathlib import Path

import pytest

from sag_network.sdr import (
    CsvSdrSource,
    SdrFrame,
    SdrFrameStatus,
    SdrInTheLoopEngine,
    SdrLoopbackConfig,
    SdrSampleBlock,
    SyntheticSdrSource,
)


def config() -> SdrLoopbackConfig:
    return SdrLoopbackConfig(
        symbol_rate_hz=1000.0,
        samples_per_symbol=8,
        carrier_offset_hz=37.5,
        phase_offset_rad=0.31,
        noise_std=0.02,
    )


def frame() -> SdrFrame:
    return SdrFrame(frame_id="f1", bits=[1, 0, 1, 1, 0, 0, 1, 0])


def test_synthetic_loopback_decodes_without_errors() -> None:
    result = SdrInTheLoopEngine().process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    assert result.decoded_frame_count == 1
    assert result.total_bit_errors == 0
    assert result.mean_ber == 0.0
    assert result.external_hardware_used is False
    assert result.network_mutation is False


def test_frequency_offset_is_estimated() -> None:
    result = SdrInTheLoopEngine().process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    assert result.estimated_frequency_offset_hz == pytest.approx(37.5, abs=1.0)


def test_sample_count_matches_symbols() -> None:
    result = SdrInTheLoopEngine().process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    assert result.sample_count == len(frame().bits) * config().samples_per_symbol


def test_processing_fingerprint_is_deterministic() -> None:
    engine = SdrInTheLoopEngine()
    first = engine.process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    second = engine.process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    assert first.sample_fingerprint == second.sample_fingerprint
    assert first.processing_fingerprint == second.processing_fingerprint


def test_different_seed_changes_sample_fingerprint() -> None:
    engine = SdrInTheLoopEngine()
    first = engine.process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    second = engine.process(
        frame=frame(), config=config(), source=SyntheticSdrSource(seed=4301), timestamp_s=1.0
    )
    assert first.sample_fingerprint != second.sample_fingerprint


def test_frame_rejected_when_noise_causes_errors() -> None:
    noisy = config().model_copy(update={"noise_std": 3.0})
    result = SdrInTheLoopEngine().process(
        frame=frame(), config=noisy, source=SyntheticSdrSource(seed=4300), timestamp_s=1.0
    )
    assert result.total_bit_errors > 0
    assert result.mean_ber > 0.0


def test_iq_lengths_must_match() -> None:
    with pytest.raises(ValueError, match="sample counts"):
        SdrSampleBlock(
            timestamp_s=0.0,
            sample_rate_hz=1000.0,
            center_frequency_hz=0.0,
            i_samples=[1.0],
            q_samples=[0.0, 0.0],
        )


def test_bits_must_be_binary() -> None:
    with pytest.raises(ValueError, match="binary"):
        SdrFrame(frame_id="bad", bits=[0, 1, 2])


def test_invalid_iq_csv_columns_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "capture.csv"
    path.write_text("i,x\n1,2\n", encoding="utf-8")
    source = CsvSdrSource(path, sample_rate_hz=1000.0)
    with pytest.raises(ValueError, match="i and q columns"):
        source.capture(frame(), config(), 0.0)


def test_csv_source_reads_iq_samples(tmp_path: Path) -> None:
    path = tmp_path / "capture.csv"
    path.write_text("i,q\n1,0\n0.5,-0.5\n", encoding="utf-8")
    source = CsvSdrSource(path, sample_rate_hz=1000.0, center_frequency_hz=915e6)
    block = source.capture(frame(), config(), 2.0)
    assert block.i_samples == [1.0, 0.5]
    assert block.q_samples == [0.0, -0.5]
    assert block.center_frequency_hz == 915e6


def test_decode_reports_decoded_status_for_clean_samples() -> None:
    source = SyntheticSdrSource(seed=4300)
    block = source.capture(frame(), config(), 0.0)
    result = SdrInTheLoopEngine().decode(frame(), block, config())
    assert result.status is SdrFrameStatus.DECODED


def test_decode_rejects_truncated_capture() -> None:
    source = SyntheticSdrSource(seed=4300)
    block = source.capture(frame(), config(), 0.0)
    truncated = block.model_copy(
        update={"i_samples": block.i_samples[:-1], "q_samples": block.q_samples[:-1]}
    )
    result = SdrInTheLoopEngine().decode(frame(), truncated, config())
    assert result.status is SdrFrameStatus.REJECTED
    assert result.bit_errors > 0


def test_config_rejects_non_positive_symbol_rate() -> None:
    with pytest.raises(ValueError):
        SdrLoopbackConfig(symbol_rate_hz=0, samples_per_symbol=8)
