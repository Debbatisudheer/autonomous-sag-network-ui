from __future__ import annotations

import hashlib
import json
import zlib

from sag_network.wireless.models import (
    WirelessIntegrationConfig,
    WirelessIntegrationReport,
    WirelessPacket,
)
from sag_network.wireless.transport import WirelessTransport


class RealWirelessNetworkIntegrationEngine:
    """Builds verified packets and executes them through a wireless transport boundary."""

    def process(
        self,
        *,
        config: WirelessIntegrationConfig,
        transport: WirelessTransport,
    ) -> WirelessIntegrationReport:
        packet = WirelessPacket(
            sequence=config.sequence,
            source_id=config.source_id,
            destination_id=config.destination_id,
            payload=config.payload,
            timestamp_s=config.timestamp_s,
            checksum_hex=self._checksum(config.payload),
        )
        response, exchange = transport.exchange(packet, config.timeout_s)
        checksum_valid = (
            response is not None and self._checksum(response.payload) == packet.checksum_hex
        )
        delivered = response is not None and checksum_valid and response.payload == packet.payload
        packet_fingerprint = self._fingerprint(packet.model_dump(mode="json"))
        exchange_fingerprint = self._fingerprint({
            "packet": packet.model_dump(mode="json"),
            "response": response.model_dump(mode="json") if response is not None else None,
            "exchange": exchange.model_dump(mode="json"),
            "delivered": delivered,
        })
        return WirelessIntegrationReport(
            timestamp_s=config.timestamp_s,
            sequence=config.sequence,
            transport=exchange.transport,
            bytes_sent=exchange.bytes_sent,
            bytes_received=exchange.bytes_received,
            latency_ms=exchange.latency_ms,
            packet_loss=exchange.packet_loss,
            checksum_valid=checksum_valid,
            delivered=delivered,
            packet_fingerprint=packet_fingerprint,
            exchange_fingerprint=exchange_fingerprint,
            external_network_used=exchange.external_network_used,
            network_mutation=False,
        )

    @staticmethod
    def _checksum(payload: bytes) -> str:
        return f"{zlib.crc32(payload) & 0xFFFFFFFF:08x}"

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()


__all__ = ["RealWirelessNetworkIntegrationEngine"]
