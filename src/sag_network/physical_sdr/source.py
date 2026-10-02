from __future__ import annotations

import importlib
import math
import random
from typing import Any, Protocol, cast

from sag_network.physical_sdr.models import (
    PhysicalSdrCapture,
    PhysicalSdrConfig,
    PhysicalSdrDeviceInfo,
)


class PhysicalSdrBackend(Protocol):
    """Small RX-only backend boundary shared by real and test hardware adapters."""

    @property
    def device_name(self) -> str:
        ...

    def configure(self, config: PhysicalSdrConfig) -> None:
        ...

    def receive(self, sample_count: int, timeout_us: int) -> tuple[list[float], list[float]]:
        ...

    def close(self) -> None:
        ...


class SyntheticPhysicalSdrBackend:
    """Deterministic backend that exercises the physical-SDR integration boundary."""

    def __init__(self, *, seed: int = 6700) -> None:
        self._seed = seed
        self._device_name = "synthetic-rx-backend"
        self._sample_rate_hz = 1.0
        self._center_frequency_hz = 0.0

    @property
    def device_name(self) -> str:
        return self._device_name

    def configure(self, config: PhysicalSdrConfig) -> None:
        self._sample_rate_hz = config.sample_rate_hz
        self._center_frequency_hz = config.center_frequency_hz

    def receive(self, sample_count: int, timeout_us: int) -> tuple[list[float], list[float]]:
        del timeout_us
        rng = random.Random(self._seed + sample_count)
        i_samples: list[float] = []
        q_samples: list[float] = []
        for index in range(sample_count):
            phase = 2.0 * math.pi * 125.0 * index / self._sample_rate_hz
            i_samples.append(0.8 * math.cos(phase) + rng.gauss(0.0, 0.01))
            q_samples.append(0.4 * math.sin(phase) + rng.gauss(0.0, 0.01))
        return i_samples, q_samples

    def close(self) -> None:
        return None


class SoapySdrRxBackend:
    """RX-only SoapySDR backend. It never creates or activates a TX stream."""

    def __init__(self, device_args: str = "") -> None:
        try:
            soapysdr = cast(Any, importlib.import_module("SoapySDR"))
            numpy = cast(Any, importlib.import_module("numpy"))
        except ImportError as exc:
            raise RuntimeError(
                "physical SDR mode requires SoapySDR and numpy to be installed"
            ) from exc

        self._soapy = soapysdr
        self._numpy = numpy
        args = self._parse_device_args(device_args)
        self._device = self._soapy.Device(args)
        self._stream: Any | None = None
        self._channel = 0

        hardware = self._device.getHardwareInfo()
        driver = str(hardware.get("driver", "unknown"))
        label = str(hardware.get("label", ""))
        self._device_name = f"{driver}:{label}".strip(":") or "soapy-sdr"

    @staticmethod
    def _parse_device_args(device_args: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for item in device_args.split(",") if device_args else []:
            if not item.strip():
                continue
            if "=" not in item:
                raise ValueError("SoapySDR device args must use key=value pairs")
            key, value = item.split("=", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    @property
    def device_name(self) -> str:
        return self._device_name

    def configure(self, config: PhysicalSdrConfig) -> None:
        self._channel = config.channel
        direction = self._soapy.SOAPY_SDR_RX
        format_code = self._soapy.SOAPY_SDR_CF32
        self._device.setSampleRate(direction, self._channel, config.sample_rate_hz)
        self._device.setFrequency(direction, self._channel, config.center_frequency_hz)
        if config.bandwidth_hz is not None:
            self._device.setBandwidth(direction, self._channel, config.bandwidth_hz)
        if config.gain_db is not None:
            self._device.setGain(direction, self._channel, config.gain_db)
        if config.antenna is not None:
            self._device.setAntenna(direction, self._channel, config.antenna)
        self._stream = self._device.setupStream(direction, format_code, [self._channel])
        self._device.activateStream(self._stream)

    def receive(self, sample_count: int, timeout_us: int) -> tuple[list[float], list[float]]:
        if self._stream is None:
            raise RuntimeError("SDR backend is not configured")
        buffer = self._numpy.empty(sample_count, dtype=self._numpy.complex64)
        result = self._device.readStream(
            self._stream,
            [buffer],
            sample_count,
            timeoutUs=timeout_us,
        )
        returned = int(getattr(result, "ret", -1))
        if returned <= 0:
            raise RuntimeError(f"SoapySDR readStream failed with code {returned}")
        samples = buffer[:returned]
        real = cast(Any, samples.real)
        imag = cast(Any, samples.imag)
        return [float(value) for value in real], [float(value) for value in imag]

    def close(self) -> None:
        if self._stream is not None:
            self._device.deactivateStream(self._stream)
            self._device.closeStream(self._stream)
            self._stream = None


def discover_soapysdr_devices() -> list[PhysicalSdrDeviceInfo]:
    """Discover physically connected SoapySDR devices without opening a stream."""
    try:
        soapysdr = cast(Any, importlib.import_module("SoapySDR"))
    except ImportError as exc:
        raise RuntimeError(
            "physical SDR discovery requires SoapySDR to be installed"
        ) from exc

    devices: list[PhysicalSdrDeviceInfo] = []
    raw_devices = soapysdr.Device.enumerate()
    for raw in raw_devices:
        values = dict(raw)
        devices.append(
            PhysicalSdrDeviceInfo(
                driver=str(values.get("driver", "unknown")),
                hardware=str(values.get("hardware", "")),
                serial=str(values.get("serial", "")),
                label=str(values.get("label", "")),
                args=str(values),
            )
        )
    return devices


class PhysicalSdrSource:
    """Capture one RX-only IQ block through a physical or test backend."""

    def __init__(self, backend: PhysicalSdrBackend) -> None:
        self._backend = backend

    @property
    def external_hardware_used(self) -> bool:
        return not isinstance(self._backend, SyntheticPhysicalSdrBackend)

    def capture(self, config: PhysicalSdrConfig, timestamp_s: float) -> PhysicalSdrCapture:
        self._backend.configure(config)
        try:
            i_samples, q_samples = self._backend.receive(
                config.sample_count,
                config.timeout_us,
            )
        finally:
            self._backend.close()

        if not i_samples or len(i_samples) != len(q_samples):
            raise RuntimeError("SDR backend returned an invalid I/Q capture")

        return PhysicalSdrCapture(
            timestamp_s=timestamp_s,
            sample_rate_hz=config.sample_rate_hz,
            center_frequency_hz=config.center_frequency_hz,
            channel=config.channel,
            i_samples=i_samples,
            q_samples=q_samples,
            hardware_device=self._backend.device_name,
        )


__all__ = [
    "PhysicalSdrBackend",
    "PhysicalSdrSource",
    "SoapySdrRxBackend",
    "SyntheticPhysicalSdrBackend",
    "discover_soapysdr_devices",
]
