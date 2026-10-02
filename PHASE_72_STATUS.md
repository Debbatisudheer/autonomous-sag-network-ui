# Phase 72 — Hardware + SDR Closed Loop

Phase 72 composes the validated Phase 71 edge workload, the Phase 67 RX-only SDR capture/measurement boundary, and the Phase 69 software wireless-link framing boundary into a single closed-loop execution path.

Evidence modes:

- `SYNTHETIC FIXTURE`: deterministic edge + synthetic SDR + deterministic software link.
- `LOCAL HOST MEASUREMENT`: edge workload executes on the current host while SDR/link remain synthetic.
- `HARDWARE MEASUREMENT`: RX I/Q is captured from a physically connected SoapySDR device; the derived control payload is then checked through the deterministic software link path.

No TX SDR path is implemented. No external network is required or mutated. A hardware claim requires successful `--hardware` execution against a real RX-capable SoapySDR device.

Status: IN PROGRESS pending Windows Ruff, mypy, pytest, and runtime validation. An inherited typing continuity defect in `hardware_sdr_closed_loop/engine.py` was corrected by importing the concrete `HardwareEdgeDeploymentReport` and `PhysicalSdrReport` model types.
