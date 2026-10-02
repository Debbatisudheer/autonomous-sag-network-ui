# Phase 68 — Physical RF Measurement

Status: IMPLEMENTED, awaiting Windows validation.

Phase 68 extends the RX-only physical SDR boundary from Phase 67 into deterministic RF measurement primitives over captured complex I/Q samples.

## Measurements

- normalized mean I/Q power
- RMS amplitude
- peak amplitude
- crest factor
- estimated noise power using a lower-power fraction of samples
- estimated signal power
- SNR estimate in dB
- dynamic-range estimate in dB
- I/Q DC-offset magnitude
- deterministic sample and measurement fingerprints

Absolute calibrated dBm is intentionally not claimed; calibrated RF power requires receiver/device calibration metadata that is not established by this software alone.

## Evidence boundary

Default validation uses the deterministic synthetic RX fixture and is classified as `SYNTHETIC FIXTURE`.

`--hardware` uses the Phase 67 SoapySDR RX-only backend and is classified as `HARDWARE MEASUREMENT` only when an actual RX-capable physical SDR successfully supplies the capture.

No transmit path is introduced. No network mutation is performed by the phase runner.

## Continuity

The Phase 67 inherited `Mapping[str, object]` fingerprint typing correction is retained.
The previously validated ISO-8601 timestamp correction and all earlier locked phase corrections are carried forward.
