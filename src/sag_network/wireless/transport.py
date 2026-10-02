from __future__ import annotations

import socket
import time
from abc import ABC, abstractmethod

from sag_network.wireless.models import WirelessExchange, WirelessPacket, WirelessTransportKind


class WirelessTransport(ABC):
    """Transport boundary for real or deterministic wireless network adapters."""

    @property
    @abstractmethod
    def kind(self) -> WirelessTransportKind:
        raise NotImplementedError

    @property
    @abstractmethod
    def external_network_used(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def exchange(
        self, packet: WirelessPacket, timeout_s: float
    ) -> tuple[WirelessPacket | None, WirelessExchange]:
        raise NotImplementedError


class SyntheticWirelessTransport(WirelessTransport):
    """Deterministic in-memory loopback used for offline validation."""

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
        echoed = packet.model_copy(deep=True)
        exchange = WirelessExchange(
            sequence=packet.sequence,
            bytes_sent=len(packet.payload),
            bytes_received=len(echoed.payload),
            latency_ms=0.0,
            packet_loss=False,
            checksum_valid=True,
            transport=self.kind,
            external_network_used=False,
        )
        return echoed, exchange


class UdpWirelessTransport(WirelessTransport):
    """Real UDP network adapter; not invoked by offline validation scripts."""

    def __init__(
        self, *, bind_host: str, bind_port: int, remote_host: str, remote_port: int
    ) -> None:
        self._bind_host = bind_host
        self._bind_port = bind_port
        self._remote = (remote_host, remote_port)

    @property
    def kind(self) -> WirelessTransportKind:
        return WirelessTransportKind.UDP

    @property
    def external_network_used(self) -> bool:
        return True

    def exchange(
        self, packet: WirelessPacket, timeout_s: float
    ) -> tuple[WirelessPacket | None, WirelessExchange]:
        started = time.monotonic()
        encoded = packet.payload
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((self._bind_host, self._bind_port))
            sock.settimeout(timeout_s)
            sock.sendto(encoded, self._remote)
            try:
                payload, _ = sock.recvfrom(max(65535, len(encoded)))
            except TimeoutError:
                exchange = WirelessExchange(
                    sequence=packet.sequence,
                    bytes_sent=len(encoded),
                    bytes_received=0,
                    latency_ms=(time.monotonic() - started) * 1000.0,
                    packet_loss=True,
                    checksum_valid=False,
                    transport=self.kind,
                    external_network_used=True,
                )
                return None, exchange
        echoed = packet.model_copy(update={"payload": payload})
        exchange = WirelessExchange(
            sequence=packet.sequence,
            bytes_sent=len(encoded),
            bytes_received=len(payload),
            latency_ms=(time.monotonic() - started) * 1000.0,
            packet_loss=False,
            checksum_valid=True,
            transport=self.kind,
            external_network_used=True,
        )
        return echoed, exchange


__all__ = ["SyntheticWirelessTransport", "UdpWirelessTransport", "WirelessTransport"]
