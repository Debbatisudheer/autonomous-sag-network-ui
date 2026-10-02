from __future__ import annotations

import argparse
import json

from sag_network.physical_wireless_link import (
    PhysicalWirelessLinkConfig,
    PhysicalWirelessLinkEngine,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 69 physical wireless link validation")
    parser.add_argument("--payload", default="SAG-PHASE-69")
    args = parser.parse_args()
    config = PhysicalWirelessLinkConfig(
        source_id="ground-node-01",
        destination_id="air-node-01",
        payload=args.payload.encode("utf-8"),
        sample_rate_hz=2_000_000.0,
        symbol_rate_hz=100_000.0,
        amplitude=0.8,
        decision_threshold=0.5,
    )
    report = PhysicalWirelessLinkEngine().process_synthetic(
        config=config,
        timestamp_s=69.0,
    )
    print(json.dumps({
        "name": "Physical Wireless Link",
        "phase": "69",
        "status": "pass" if report.delivered else "fail",
        "evidence_class": report.evidence_class.value,
        "source_id": report.source_id,
        "destination_id": report.destination_id,
        "payload_bytes": report.payload_bytes,
        "encoded_bytes": report.encoded_bytes,
        "sample_count": report.sample_count,
        "transmitted_bit_count": report.transmitted_bit_count,
        "received_bit_count": report.received_bit_count,
        "bit_error_rate": report.bit_error_rate,
        "crc_valid": report.crc_valid,
        "delivered": report.delivered,
        "sample_fingerprint": report.sample_fingerprint,
        "link_fingerprint": report.link_fingerprint,
        "external_hardware_used": report.external_hardware_used,
        "network_mutation": report.network_mutation,
        "notice": "Default mode is a deterministic synthetic baseband link. Physical RF evidence requires a compatible receive capture from an actual wireless link and calibrated receiver chain.",
    }, sort_keys=False, indent=2))


if __name__ == "__main__":
    main()
