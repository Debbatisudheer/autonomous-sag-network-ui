from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

from sag_network.physical_rf.models import (
    PhysicalRfEvidence,
    PhysicalRfMeasurementConfig,
    PhysicalRfReport,
)
from sag_network.physical_sdr.models import PhysicalSdrCapture


class PhysicalRfMeasurementEngine:
    """Derive deterministic RX-only RF measurements from captured complex I/Q samples."""

    def measure(
        self,
        *,
        capture: PhysicalSdrCapture,
        evidence_class: PhysicalRfEvidence,
        external_hardware_used: bool,
        config: PhysicalRfMeasurementConfig | None = None,
    ) -> PhysicalRfReport:
        effective = config or PhysicalRfMeasurementConfig(
            noise_floor_fraction=0.25,
            min_noise_power=1e-12,
        )
        i_values = capture.i_samples
        q_values = capture.q_samples
        sample_count = len(i_values)
        if sample_count == 0 or sample_count != len(q_values):
            raise ValueError("I/Q capture must contain equal non-empty sample arrays")

        mean_i = sum(i_values) / sample_count
        mean_q = sum(q_values) / sample_count
        powers = [i_value * i_value + q_value * q_value for i_value, q_value in zip(i_values, q_values, strict=True)]
        amplitudes = [math.sqrt(power) for power in powers]
        mean_power = sum(powers) / sample_count
        rms_amplitude = math.sqrt(mean_power)
        peak_amplitude = max(amplitudes)
        crest_factor = 0.0 if rms_amplitude <= 1e-12 else peak_amplitude / rms_amplitude

        sorted_powers = sorted(powers)
        noise_count = max(1, math.ceil(sample_count * effective.noise_floor_fraction))
        noise_power = max(
            effective.min_noise_power,
            sum(sorted_powers[:noise_count]) / noise_count,
        )
        signal_power = max(0.0, mean_power - noise_power)
        snr_db = (
            10.0 * math.log10(signal_power / noise_power)
            if signal_power > 0.0
            else float("-inf")
        )
        positive_amplitudes = [value for value in amplitudes if value > 1e-12]
        min_amplitude = min(positive_amplitudes) if positive_amplitudes else 1e-12
        dynamic_range_db = 20.0 * math.log10(max(peak_amplitude, 1e-12) / min_amplitude)
        dc_offset_magnitude = math.hypot(mean_i, mean_q)

        sample_payload = {
            "timestamp_s": capture.timestamp_s,
            "sample_rate_hz": capture.sample_rate_hz,
            "center_frequency_hz": capture.center_frequency_hz,
            "channel": capture.channel,
            "i_samples": i_values,
            "q_samples": q_values,
            "hardware_device": capture.hardware_device,
        }
        measurement_payload = {
            "capture": sample_payload,
            "config": effective.model_dump(mode="json"),
            "evidence_class": evidence_class.value,
            "external_hardware_used": external_hardware_used,
            "mean_i": mean_i,
            "mean_q": mean_q,
            "dc_offset_magnitude": dc_offset_magnitude,
            "mean_power_normalized": mean_power,
            "rms_amplitude": rms_amplitude,
            "peak_amplitude": peak_amplitude,
            "crest_factor": crest_factor,
            "noise_power_normalized": noise_power,
            "signal_power_normalized": signal_power,
            "snr_db_estimate": snr_db,
            "dynamic_range_db": dynamic_range_db,
        }
        return PhysicalRfReport(
            timestamp_s=capture.timestamp_s,
            sample_count=sample_count,
            sample_rate_hz=capture.sample_rate_hz,
            center_frequency_hz=capture.center_frequency_hz,
            channel=capture.channel,
            mean_i=mean_i,
            mean_q=mean_q,
            dc_offset_magnitude=dc_offset_magnitude,
            mean_power_normalized=mean_power,
            rms_amplitude=rms_amplitude,
            peak_amplitude=peak_amplitude,
            crest_factor=crest_factor,
            noise_power_normalized=noise_power,
            signal_power_normalized=signal_power,
            snr_db_estimate=snr_db,
            dynamic_range_db=dynamic_range_db,
            sample_fingerprint=self._fingerprint(sample_payload),
            measurement_fingerprint=self._fingerprint(measurement_payload),
            evidence_class=evidence_class,
            external_hardware_used=external_hardware_used,
            network_mutation=False,
        )

    @staticmethod
    def _fingerprint(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["PhysicalRfMeasurementEngine"]
