from __future__ import annotations

import hashlib
import json
import zlib
from collections.abc import Mapping

from sag_network.physical_sdr.models import PhysicalSdrCapture
from sag_network.physical_wireless_link.models import (
    PhysicalWirelessEvidence,
    PhysicalWirelessFrame,
    PhysicalWirelessLinkConfig,
    PhysicalWirelessLinkReport,
)


class PhysicalWirelessLinkEngine:
    """RX-focused baseband link framing and deterministic OOK validation boundary."""

    _VERSION = 1
    _HEADER_SIZE = 4
    _CRC_SIZE = 4

    def build_frame(self, config: PhysicalWirelessLinkConfig) -> PhysicalWirelessFrame:
        encoded = self._encode_frame(config)
        crc = zlib.crc32(config.payload) & 0xFFFFFFFF
        return PhysicalWirelessFrame(
            source_id=config.source_id,
            destination_id=config.destination_id,
            payload=config.payload,
            encoded_bytes=encoded,
            bit_count=len(encoded) * 8,
            crc32_hex=f"{crc:08x}",
        )

    def modulate_ook(self, frame: PhysicalWirelessFrame, config: PhysicalWirelessLinkConfig) -> tuple[list[float], list[float]]:
        samples_per_symbol = config.samples_per_symbol
        bits = self._bytes_to_bits(config.preamble_bytes + frame.encoded_bytes)
        i_samples: list[float] = []
        q_samples: list[float] = []
        for bit in bits:
            level = config.amplitude if bit else 0.0
            i_samples.extend([level] * samples_per_symbol)
            q_samples.extend([0.0] * samples_per_symbol)
        return i_samples, q_samples

    def decode_ook(
        self,
        capture: PhysicalSdrCapture,
        config: PhysicalWirelessLinkConfig,
    ) -> tuple[PhysicalWirelessFrame | None, int, int]:
        samples_per_symbol = config.samples_per_symbol
        usable = len(capture.i_samples) - (len(capture.i_samples) % samples_per_symbol)
        if usable < samples_per_symbol:
            return None, 0, 0
        threshold = config.amplitude * config.decision_threshold
        bits: list[int] = []
        for start in range(0, usable, samples_per_symbol):
            center = start + (samples_per_symbol // 2)
            bits.append(1 if abs(capture.i_samples[center]) >= threshold else 0)
        decoded = self._bits_to_bytes(bits)
        preamble = config.preamble_bytes
        for preamble_start in range(0, len(decoded) - len(preamble) + 1):
            if decoded[preamble_start : preamble_start + len(preamble)] != preamble:
                continue
            offset = preamble_start + len(preamble)
            if len(decoded) - offset < self._HEADER_SIZE + self._CRC_SIZE:
                continue
            if decoded[offset] != self._VERSION:
                continue
            payload_length = int.from_bytes(decoded[offset + 2 : offset + 4], "big")
            frame_end = offset + self._HEADER_SIZE + payload_length + self._CRC_SIZE
            if frame_end > len(decoded):
                continue
            payload = decoded[offset + self._HEADER_SIZE : offset + self._HEADER_SIZE + payload_length]
            expected_crc = int.from_bytes(decoded[offset + self._HEADER_SIZE + payload_length : frame_end], "big")
            actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
            if payload_length < 1 or expected_crc != actual_crc:
                continue
            frame = PhysicalWirelessFrame(
                source_id=config.source_id,
                destination_id=config.destination_id,
                payload=payload,
                encoded_bytes=decoded[offset:frame_end],
                bit_count=(frame_end - offset) * 8,
                crc32_hex=f"{expected_crc:08x}",
            )
            return frame, (frame_end - preamble_start) * 8, frame_end
        return None, 0, 0

    def process_synthetic(
        self,
        *,
        config: PhysicalWirelessLinkConfig,
        timestamp_s: float,
        evidence_class: PhysicalWirelessEvidence = PhysicalWirelessEvidence.SYNTHETIC_FIXTURE,
    ) -> PhysicalWirelessLinkReport:
        _ = timestamp_s
        frame = self.build_frame(config)
        i_samples, q_samples = self.modulate_ook(frame, config)
        capture = PhysicalSdrCapture(
            timestamp_s=timestamp_s,
            sample_rate_hz=config.sample_rate_hz,
            center_frequency_hz=0.0,
            channel=0,
            i_samples=i_samples,
            q_samples=q_samples,
            hardware_device="synthetic-ook-link",
        )
        return self.process_capture(
            capture=capture,
            config=config,
            evidence_class=evidence_class,
            external_hardware_used=False,
        )

    def process_capture(
        self,
        *,
        capture: PhysicalSdrCapture,
        config: PhysicalWirelessLinkConfig,
        evidence_class: PhysicalWirelessEvidence,
        external_hardware_used: bool,
    ) -> PhysicalWirelessLinkReport:
        frame = self.build_frame(config)
        received_frame, received_bit_count, _ = self.decode_ook(capture, config)
        return self._report(
            frame=frame,
            capture=capture,
            config=config,
            evidence_class=evidence_class,
            external_hardware_used=external_hardware_used,
            received_frame=received_frame,
            received_bit_count=received_bit_count,
        )

    def _report(
        self,
        *,
        frame: PhysicalWirelessFrame,
        capture: PhysicalSdrCapture,
        config: PhysicalWirelessLinkConfig,
        evidence_class: PhysicalWirelessEvidence,
        external_hardware_used: bool,
        received_frame: PhysicalWirelessFrame | None,
        received_bit_count: int,
    ) -> PhysicalWirelessLinkReport:
        transmitted_bits = self._bytes_to_bits(config.preamble_bytes + frame.encoded_bytes)
        received_bits = (
            self._bytes_to_bits(config.preamble_bytes + received_frame.encoded_bytes)
            if received_frame is not None
            else []
        )
        compare_count = min(len(transmitted_bits), len(received_bits))
        bit_errors = sum(
            transmitted_bits[index] != received_bits[index]
            for index in range(compare_count)
        ) + abs(len(transmitted_bits) - len(received_bits))
        bit_error_rate = bit_errors / len(transmitted_bits) if transmitted_bits else 0.0
        crc_valid = received_frame is not None
        delivered = (
            received_frame is not None
            and received_frame.payload == frame.payload
            and received_frame.crc32_hex == frame.crc32_hex
        )
        sample_payload = {
            "sample_rate_hz": capture.sample_rate_hz,
            "center_frequency_hz": capture.center_frequency_hz,
            "channel": capture.channel,
            "i_samples": capture.i_samples,
            "q_samples": capture.q_samples,
            "hardware_device": capture.hardware_device,
        }
        link_payload: Mapping[str, object] = {
            "frame": frame.model_dump(mode="python"),
            "received_frame": received_frame.model_dump(mode="python") if received_frame else None,
            "config": config.model_dump(mode="python"),
            "received_bit_count": received_bit_count,
            "bit_errors": bit_errors,
            "bit_error_rate": bit_error_rate,
            "delivered": delivered,
            "crc_valid": crc_valid,
            "evidence_class": evidence_class.value,
            "external_hardware_used": external_hardware_used,
        }
        return PhysicalWirelessLinkReport(
            source_id=config.source_id,
            destination_id=config.destination_id,
            payload_bytes=len(config.payload),
            encoded_bytes=len(frame.encoded_bytes),
            transmitted_bit_count=len(transmitted_bits),
            received_bit_count=received_bit_count,
            received_bits=compare_count,
            bit_errors=bit_errors,
            bit_error_rate=bit_error_rate,
            delivered=delivered,
            crc_valid=crc_valid,
            sample_count=len(capture.i_samples),
            sample_rate_hz=capture.sample_rate_hz,
            symbol_rate_hz=config.symbol_rate_hz,
            sample_fingerprint=self._fingerprint(sample_payload),
            link_fingerprint=self._fingerprint(link_payload),
            evidence_class=evidence_class,
            external_hardware_used=external_hardware_used,
            network_mutation=False,
        )

    def _encode_frame(self, config: PhysicalWirelessLinkConfig) -> bytes:
        if len(config.payload) > 1024:
            raise ValueError("payload exceeds physical link frame limit")
        source_crc = zlib.crc32(config.payload) & 0xFFFFFFFF
        return bytes([self._VERSION, 0]) + len(config.payload).to_bytes(2, "big") + config.payload + source_crc.to_bytes(4, "big")

    @staticmethod
    def _bytes_to_bits(value: bytes) -> list[int]:
        bits: list[int] = []
        for byte in value:
            bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
        return bits

    @staticmethod
    def _bits_to_bytes(bits: list[int]) -> bytes:
        if len(bits) < 8:
            return b""
        whole = len(bits) - (len(bits) % 8)
        output = bytearray()
        for start in range(0, whole, 8):
            value = 0
            for bit in bits[start : start + 8]:
                value = (value << 1) | bit
            output.append(value)
        return bytes(output)

    @staticmethod
    def _fingerprint(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["PhysicalWirelessLinkEngine"]
