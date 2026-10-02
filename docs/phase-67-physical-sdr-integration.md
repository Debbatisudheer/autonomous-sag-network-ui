# Phase 67 — Physical SDR Integration

## Scope

Phase 67 adds an explicit physical SDR integration boundary on top of the locked Phase 66 online-adaptation baseline.

The integration is **RX-only**. It provides:

- typed physical SDR configuration;
- SoapySDR device discovery;
- an RX-only SoapySDR backend;
- sample-rate, center-frequency, bandwidth, gain, antenna, channel, and receive-timeout configuration;
- physical I/Q capture normalization;
- deterministic processing fingerprints;
- a synthetic backend for hardware-free validation;
- explicit evidence classification between `SYNTHETIC FIXTURE` and `HARDWARE MEASUREMENT`;
- an explicit `external_hardware_used` flag;
- no transmit path and no network mutation.

## Evidence boundary

The default Phase 67 validation uses `SyntheticPhysicalSdrBackend`, so it is not a physical hardware measurement.

The `SoapySdrRxBackend` is the physical hardware integration boundary. It is not invoked by the default validation because actual device availability is environment-dependent.

Physical mode is deliberately RX-only and does not create or activate a transmit stream.

## Validation

```powershell
ruff check . --fix
ruff check .
mypy src
pytest -q
python scripts\run_phase67_physical_sdr_integration.py
```

A physical measurement may be performed only on a machine with SoapySDR, NumPy, and a connected RX-capable SDR:

```powershell
python scripts\run_phase67_physical_sdr_integration.py --hardware --hardware-device-args "driver=..."
```

The hardware command's successful output is classified as `HARDWARE MEASUREMENT` and is the only basis for claiming physical SDR capture evidence.
