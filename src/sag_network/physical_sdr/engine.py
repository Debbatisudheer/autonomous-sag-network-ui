from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

from sag_network.physical_sdr.models import (
    PhysicalSdrCapture,
    PhysicalSdrConfig,
    PhysicalSdrEvidence,
    PhysicalSdrReport,
)
from sag_network.physical_sdr.source import PhysicalSdrSource


class PhysicalSdrIntegrationEngine:
    """Processes RX IQ measurements without transmitting or mutating network state."""

    def process(
        self,
        *,
        source: PhysicalSdrSource,
        config: PhysicalSdrConfig,
        timestamp_s: float,
        evidence_class: PhysicalSdrEvidence,
    ) -> PhysicalSdrReport:
        capture = source.capture(config, timestamp_s)
        sample_count = len(capture.i_samples)
        mean_i = sum(capture.i_samples) / sample_count
        mean_q = sum(capture.q_samples) / sample_count
        i_power = sum(value * value for value in capture.i_samples) / sample_count
        q_power = sum(value * value for value in capture.q_samples) / sample_count
        mean_power = (i_power + q_power) / 2.0
        iq_imbalance_ratio = (
            0.0
            if max(i_power, q_power) <= 1e-12
            else abs(i_power - q_power) / max(i_power, q_power)
        )

        sample_payload = capture.model_dump(mode="json")
        processing_payload = {
            "config": config.model_dump(mode="json"),
            "capture": capture.model_dump(mode="json"),
            "evidence_class": evidence_class.value,
        }

        return PhysicalSdrReport(
            timestamp_s=timestamp_s,
            sample_count=sample_count,
            sample_rate_hz=capture.sample_rate_hz,
            center_frequency_hz=capture.center_frequency_hz,
            channel=capture.channel,
            mean_i=mean_i,
            mean_q=mean_q,
            mean_power=mean_power,
            iq_imbalance_ratio=iq_imbalance_ratio,
            sample_fingerprint=self._fingerprint(sample_payload),
            processing_fingerprint=self._fingerprint(processing_payload),
            evidence_class=evidence_class,
            external_hardware_used=source.external_hardware_used,
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


__all__ = ["PhysicalSdrIntegrationEngine"]
