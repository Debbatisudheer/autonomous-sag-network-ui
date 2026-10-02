from __future__ import annotations

import hashlib
import json
import math

from sag_network.sdr.models import (
    SdrDecodeResult,
    SdrFrame,
    SdrFrameStatus,
    SdrLoopbackConfig,
    SdrLoopbackReport,
    SdrSampleBlock,
)
from sag_network.sdr.source import SdrSampleSource


class SdrInTheLoopEngine:
    """Runs deterministic IQ capture, carrier estimation, demodulation, and validation."""

    def process(
        self,
        *,
        frame: SdrFrame,
        config: SdrLoopbackConfig,
        source: SdrSampleSource,
        timestamp_s: float,
    ) -> SdrLoopbackReport:
        block = source.capture(frame, config, timestamp_s)
        result = self.decode(frame, block, config)
        sample_payload = {
            "timestamp_s": block.timestamp_s,
            "sample_rate_hz": block.sample_rate_hz,
            "center_frequency_hz": block.center_frequency_hz,
            "i": block.i_samples,
            "q": block.q_samples,
        }
        sample_fingerprint = self._fingerprint(sample_payload)
        processing_fingerprint = self._fingerprint({
            "frame": frame.model_dump(mode="json"),
            "config": config.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        })
        return SdrLoopbackReport(
            timestamp_s=timestamp_s,
            sample_count=len(block.i_samples),
            frame_count=1,
            decoded_frame_count=1 if result.status is SdrFrameStatus.DECODED else 0,
            total_bit_errors=result.bit_errors,
            mean_ber=result.ber,
            mean_snr_db=result.snr_db,
            estimated_frequency_offset_hz=result.estimated_frequency_offset_hz,
            sample_fingerprint=sample_fingerprint,
            processing_fingerprint=processing_fingerprint,
            external_hardware_used=False,
            network_mutation=False,
        )

    def decode(
        self,
        frame: SdrFrame,
        block: SdrSampleBlock,
        config: SdrLoopbackConfig,
    ) -> SdrDecodeResult:
        estimated_offset = self._estimate_frequency_offset(block)
        corrected_i: list[float] = []
        corrected_q: list[float] = []
        for index, (i_value, q_value) in enumerate(zip(block.i_samples, block.q_samples)):
            phase = -2.0 * math.pi * estimated_offset * index / block.sample_rate_hz
            cosine = math.cos(phase)
            sine = math.sin(phase)
            corrected_i.append(i_value * cosine - q_value * sine)
            corrected_q.append(i_value * sine + q_value * cosine)

        decoded: list[int] = []
        for start in range(0, len(corrected_i), config.samples_per_symbol):
            stop = start + config.samples_per_symbol
            if stop > len(corrected_i):
                break
            mean_i = sum(corrected_i[start:stop]) / config.samples_per_symbol
            decoded.append(1 if mean_i >= 0 else 0)

        decoded = decoded[: len(frame.bits)]
        errors = sum(left != right for left, right in zip(decoded, frame.bits))
        errors += abs(len(frame.bits) - len(decoded))
        ber = errors / len(frame.bits)
        signal_power, noise_power = self._power_and_residual(
            corrected_i, corrected_q, config.samples_per_symbol
        )
        snr_db = 10.0 * math.log10(max(signal_power, 1e-12) / max(noise_power, 1e-12))
        status = SdrFrameStatus.DECODED if errors == 0 else SdrFrameStatus.REJECTED
        return SdrDecodeResult(
            frame_id=frame.frame_id,
            status=status,
            decoded_bits=decoded,
            bit_errors=errors,
            ber=ber,
            signal_power=signal_power,
            noise_power=noise_power,
            snr_db=snr_db,
            estimated_frequency_offset_hz=estimated_offset,
        )

    @staticmethod
    def _estimate_frequency_offset(block: SdrSampleBlock) -> float:
        if len(block.i_samples) < 2:
            return 0.0
        phase_sum = 0.0
        for previous, current in zip(
            zip(block.i_samples, block.q_samples),
            zip(block.i_samples[1:], block.q_samples[1:]),
        ):
            previous_squared_i = previous[0] * previous[0] - previous[1] * previous[1]
            previous_squared_q = 2.0 * previous[0] * previous[1]
            current_squared_i = current[0] * current[0] - current[1] * current[1]
            current_squared_q = 2.0 * current[0] * current[1]
            cross_i = previous_squared_i * current_squared_i + previous_squared_q * current_squared_q
            cross_q = previous_squared_i * current_squared_q - previous_squared_q * current_squared_i
            phase_sum += math.atan2(cross_q, cross_i)
        mean_phase = phase_sum / (len(block.i_samples) - 1)
        return mean_phase * block.sample_rate_hz / (4.0 * math.pi)

    @staticmethod
    def _power_and_residual(
        i_samples: list[float], q_samples: list[float], samples_per_symbol: int
    ) -> tuple[float, float]:
        signal_power = sum(i * i + q * q for i, q in zip(i_samples, q_samples)) / len(i_samples)
        residuals: list[float] = []
        for start in range(0, len(i_samples), samples_per_symbol):
            stop = min(start + samples_per_symbol, len(i_samples))
            mean_i = sum(i_samples[start:stop]) / (stop - start)
            mean_q = sum(q_samples[start:stop]) / (stop - start)
            magnitude = math.hypot(mean_i, mean_q)
            sign = 1.0 if mean_i >= 0.0 else -1.0
            target_i = sign * magnitude
            for i_value, q_value in zip(i_samples[start:stop], q_samples[start:stop]):
                residuals.append((i_value - target_i) ** 2 + (q_value - mean_q) ** 2)
        noise_power = sum(residuals) / len(residuals) if residuals else 0.0
        return signal_power, noise_power

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


__all__ = ["SdrInTheLoopEngine"]
