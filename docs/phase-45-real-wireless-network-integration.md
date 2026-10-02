# Phase 45 — Real Wireless Network Integration

## Scope

Phase 45 introduces the integration boundary between SAG software and a real wireless network transport.

The implementation provides:

- typed wireless packets with deterministic CRC-32 checksums;
- a transport protocol separating network integration from orchestration logic;
- a deterministic synthetic loopback transport for offline validation;
- a UDP transport adapter for real network integration;
- delivery, loss, latency, byte-count, and checksum metrics;
- deterministic packet and exchange fingerprints;
- explicit external-network evidence flags;
- no mutation of SAG network state by the integration engine.

## Evidence boundary

The Phase 45 validation script uses the synthetic transport. Its successful delivery and zero-loss result are therefore an **offline synthetic fixture**, not a measurement of a physical wireless network.

`UdpWirelessTransport` is the real network adapter boundary. It is intentionally not invoked by the offline validation script because using it would require an externally reachable UDP endpoint and would make the validation environment non-deterministic.

## Validation

The phase is ready for the Windows final gate:

```powershell
ruff check .
mypy src
pytest -q
python scripts\run_phase45_real_wireless_network.py
```
