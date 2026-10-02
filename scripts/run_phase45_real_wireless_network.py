from __future__ import annotations

import json

from sag_network.wireless import (
    RealWirelessNetworkIntegrationEngine,
    SyntheticWirelessTransport,
    WirelessIntegrationConfig,
    WirelessTransportKind,
)


def main() -> None:
    config = WirelessIntegrationConfig(
        source_id="air-node-45",
        destination_id="ground-node-45",
        payload=b"phase45-wireless-frame",
        timestamp_s=45.0,
        sequence=45,
        transport=WirelessTransportKind.SYNTHETIC,
        timeout_s=1.0,
    )
    report = RealWirelessNetworkIntegrationEngine().process(
        config=config,
        transport=SyntheticWirelessTransport(),
    )
    if not report.delivered or not report.checksum_valid:
        raise RuntimeError("phase 45 real wireless network validation failed")
    print(json.dumps({
        "name": "Real Wireless Network Integration",
        "phase": "45",
        "status": "pass",
        "transport": report.transport.value,
        "sequence": report.sequence,
        "bytes_sent": report.bytes_sent,
        "bytes_received": report.bytes_received,
        "latency_ms": report.latency_ms,
        "packet_loss": report.packet_loss,
        "checksum_valid": report.checksum_valid,
        "delivered": report.delivered,
        "packet_fingerprint": report.packet_fingerprint,
        "exchange_fingerprint": report.exchange_fingerprint,
        "external_network_used": report.external_network_used,
        "network_mutation": report.network_mutation,
        "fixture": "synthetic offline wireless transport fixture",
    }, indent=2))


if __name__ == "__main__":
    main()
