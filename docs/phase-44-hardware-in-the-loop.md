# Phase 44 — Hardware-in-the-Loop

## Scope

Phase 44 connects the locked Phase 43 SDR processing path to a typed hardware-device boundary and a deterministic offline hardware model.

The implementation provides:

- a typed `HardwareDevice` integration boundary;
- deterministic virtual RF/ADC device behavior;
- configurable hardware gain, ADC resolution, full-scale range, deterministic noise, and processing delay metadata;
- ADC quantization and clipping accounting;
- SDR IQ processing after the hardware exchange;
- deterministic sample and processing fingerprints;
- explicit external-hardware and network-mutation flags.

## Evidence boundary

The Phase 44 demo uses a **synthetic offline hardware-in-the-loop fixture**. It does not claim that physical RF hardware, an SDR board, ADC, transceiver, or external device was connected.

The `HardwareDevice` protocol is the integration boundary for a future physical adapter. The current `VirtualHardwareDevice` is a deterministic software hardware model used to validate the complete exchange and processing path.

## Validation

The phase is considered ready for the Windows final gate when Ruff, mypy, the complete pytest suite, and `scripts/run_phase44_hardware_in_the_loop.py` pass.
