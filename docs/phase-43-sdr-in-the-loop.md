# Phase 43 — SDR-in-the-Loop

## Scope

Phase 43 adds a typed SDR integration boundary and a deterministic IQ processing path on top of the locked Phase 42 edge-resource orchestration baseline.

The implementation provides:

- typed I/Q sample blocks with sample-rate and center-frequency metadata;
- an `SdrSampleSource` integration boundary;
- a deterministic synthetic IQ source for offline validation;
- a CSV IQ source for externally captured I/Q data;
- carrier-frequency-offset estimation using a BPSK-compatible squared-signal estimator;
- frequency correction and BPSK symbol decisions;
- bit-error-rate, signal-power, residual-noise-power, and SNR measurements;
- deterministic sample and processing fingerprints;
- explicit hardware and network-mutation flags.

## Evidence boundary

The Phase 43 demo uses a **synthetic offline SDR IQ loopback fixture**. It does not claim that physical SDR hardware was connected or that the measured values are field measurements.

The CSV adapter provides a path for real captured IQ data, but no external hardware is automatically opened or controlled in this phase.

## Validation

The phase is considered ready for the Windows final gate when Ruff, mypy, the complete pytest suite, and `scripts/run_phase43_sdr_in_the_loop.py` pass.
