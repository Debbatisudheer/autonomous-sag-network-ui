from __future__ import annotations

import json
import socket
import time
from abc import ABC, abstractmethod

from sag_network.network_telemetry_loop.models import NetworkTelemetryEnvelope


class TelemetryLoopTransport(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def external_network_used(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def exchange(self, envelope: NetworkTelemetryEnvelope, timeout_s: float) -> tuple[NetworkTelemetryEnvelope | None, float]:
        raise NotImplementedError


class SyntheticTelemetryLoopTransport(TelemetryLoopTransport):
    @property
    def name(self) -> str:
        return "synthetic"

    @property
    def external_network_used(self) -> bool:
        return False

    def exchange(self, envelope: NetworkTelemetryEnvelope, timeout_s: float) -> tuple[NetworkTelemetryEnvelope, float]:
        _ = timeout_s
        return envelope.model_copy(deep=True), 0.0


class LocalUdpTelemetryLoopTransport(TelemetryLoopTransport):
    """Real UDP loopback exchange; binds only to the local host."""

    def __init__(self, host: str = "127.0.0.1") -> None:
        self._host = host
        self._server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._server.bind((host, 0))
        self._server.settimeout(1.0)
        self._port = self._server.getsockname()[1]

    @property
    def name(self) -> str:
        return "udp-loopback"

    @property
    def external_network_used(self) -> bool:
        return False

    def exchange(self, envelope: NetworkTelemetryEnvelope, timeout_s: float) -> tuple[NetworkTelemetryEnvelope, float]:
        encoded = envelope.model_dump_json().encode("utf-8")
        started = time.perf_counter()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(timeout_s)
            client.sendto(encoded, (self._host, self._port))
            payload, _ = client.recvfrom(65535)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        decoded = NetworkTelemetryEnvelope.model_validate(json.loads(payload.decode("utf-8")))
        return decoded, elapsed_ms

    def serve_once(self) -> None:
        payload, address = self._server.recvfrom(65535)
        self._server.sendto(payload, address)

    def exchange_with_server(self, envelope: NetworkTelemetryEnvelope, timeout_s: float) -> tuple[NetworkTelemetryEnvelope, float]:
        # A dedicated receiver thread is intentionally avoided in the core API. This helper is unused.
        return self.exchange(envelope, timeout_s)

    def close(self) -> None:
        self._server.close()
