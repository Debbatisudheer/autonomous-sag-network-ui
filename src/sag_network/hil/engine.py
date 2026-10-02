from __future__ import annotations

import hashlib
import json

from sag_network.hil.device import HardwareDevice
from sag_network.hil.models import HardwareInTheLoopReport, HardwareLoopConfig
from sag_network.sdr import (
    SdrFrame,
    SdrInTheLoopEngine,
    SdrLoopbackConfig,
    SdrSampleSource,
)


class HardwareInTheLoopEngine:
    """Connects the SDR processing path to a hardware-compatible device boundary."""

    def process(
        self,
        *,
        frame: SdrFrame,
        sdr_config: SdrLoopbackConfig,
        source: SdrSampleSource,
        hardware_config: HardwareLoopConfig,
        device: HardwareDevice,
        timestamp_s: float,
    ) -> HardwareInTheLoopReport:
        input_block = source.capture(frame, sdr_config, timestamp_s)
        output_block, exchange = device.exchange(input_block, hardware_config, 0)
        decode = SdrInTheLoopEngine().decode(frame, output_block, sdr_config)
        sample_fingerprint = self._fingerprint(
            {
                "input": input_block.model_dump(mode="json"),
                "output": output_block.model_dump(mode="json"),
                "exchange": exchange.model_dump(mode="json"),
            }
        )
        processing_fingerprint = self._fingerprint(
            {
                "frame": frame.model_dump(mode="json"),
                "sdr_config": sdr_config.model_dump(mode="json"),
                "hardware_config": hardware_config.model_dump(mode="json"),
                "decode": decode.model_dump(mode="json"),
            }
        )
        return HardwareInTheLoopReport(
            timestamp_s=timestamp_s,
            device_id=exchange.device_id,
            cycle_count=1,
            input_sample_count=exchange.input_sample_count,
            output_sample_count=exchange.output_sample_count,
            decoded_frame_count=int(decode.status.value == "decoded"),
            total_bit_errors=decode.bit_errors,
            ber=decode.ber,
            snr_db=decode.snr_db,
            clipping_count=exchange.clipping_count,
            processing_delay_samples=exchange.processing_delay_samples,
            sample_fingerprint=sample_fingerprint,
            processing_fingerprint=processing_fingerprint,
            external_hardware_used=exchange.external_hardware_used,
            network_mutation=False,
        )

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


__all__ = ["HardwareInTheLoopEngine"]
