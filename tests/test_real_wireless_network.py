from __future__ import annotations

import pytest

from sag_network.wireless import (
    RealWirelessNetworkIntegrationEngine,
    SyntheticWirelessTransport,
    WirelessIntegrationConfig,
    WirelessPacket,
    WirelessTransport,
    WirelessTransportKind,
)
from sag_network.wireless.models import WirelessExchange


def config() -> WirelessIntegrationConfig:
    return WirelessIntegrationConfig(
        source_id="air-node-45",
        destination_id="ground-node-45",
        payload=b"phase45-wireless-frame",
        timestamp_s=45.0,
        sequence=45,
        transport=WirelessTransportKind.SYNTHETIC,
        timeout_s=1.0,
    )


def run() -> object:
    return RealWirelessNetworkIntegrationEngine().process(
        config=config(), transport=SyntheticWirelessTransport()
    )


def test_synthetic_transport_delivers_packet() -> None:
    report = run()
    assert report.delivered is True
    assert report.packet_loss is False
    assert report.checksum_valid is True
    assert report.bytes_sent == len(config().payload)
    assert report.bytes_received == len(config().payload)
    assert report.external_network_used is False
    assert report.network_mutation is False


def test_exchange_is_deterministic() -> None:
    first = run()
    second = run()
    assert first.packet_fingerprint == second.packet_fingerprint
    assert first.exchange_fingerprint == second.exchange_fingerprint


def test_payload_changes_packet_fingerprint() -> None:
    first = run()
    altered = config().model_copy(update={"payload": b"different"})
    second = RealWirelessNetworkIntegrationEngine().process(
        config=altered, transport=SyntheticWirelessTransport()
    )
    assert first.packet_fingerprint != second.packet_fingerprint


def test_sequence_is_preserved() -> None:
    assert run().sequence == 45


def test_invalid_checksum_shape_is_rejected() -> None:
    with pytest.raises(ValueError):
        WirelessPacket(
            sequence=1,
            source_id="a",
            destination_id="b",
            payload=b"x",
            timestamp_s=0.0,
            checksum_hex="not-a-crc",
        )


class CorruptTransport(WirelessTransport):
    @property
    def kind(self) -> WirelessTransportKind:
        return WirelessTransportKind.SYNTHETIC

    @property
    def external_network_used(self) -> bool:
        return False

    def exchange(
        self, packet: WirelessPacket, timeout_s: float
    ) -> tuple[WirelessPacket, WirelessExchange]:
        _ = timeout_s
        response = packet.model_copy(update={"payload": packet.payload + b"x"})
        return response, WirelessExchange(
            sequence=packet.sequence,
            bytes_sent=len(packet.payload),
            bytes_received=len(response.payload),
            latency_ms=0.0,
            packet_loss=False,
            checksum_valid=True,
            transport=self.kind,
            external_network_used=False,
        )


def test_checksum_failure_prevents_delivery() -> None:
    report = RealWirelessNetworkIntegrationEngine().process(
        config=config(), transport=CorruptTransport()
    )
    assert report.delivered is False
    assert report.checksum_valid is False
    assert report.network_mutation is False
