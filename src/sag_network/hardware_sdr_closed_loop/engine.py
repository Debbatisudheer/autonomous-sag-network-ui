from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

from sag_network.hardware_edge import (
    EdgeWorkloadSpec,
    HardwareEdgeDeploymentEngine,
    HardwareEdgeDeploymentReport,
    HardwareEdgeEvidence,
    local_host_profile,
    synthetic_device_profile,
)
from sag_network.hardware_sdr_closed_loop.models import (
    HardwareSdrClosedLoopConfig,
    HardwareSdrClosedLoopEvidence,
    HardwareSdrClosedLoopReport,
)
from sag_network.physical_sdr import (
    PhysicalSdrConfig,
    PhysicalSdrEvidence,
    PhysicalSdrIntegrationEngine,
    PhysicalSdrReport,
    PhysicalSdrSource,
    SyntheticPhysicalSdrBackend,
)
from sag_network.physical_wireless_link import (
    PhysicalWirelessEvidence,
    PhysicalWirelessLinkConfig,
    PhysicalWirelessLinkEngine,
)
from sag_network.telemetry.models import TelemetryRecord


class HardwareSdrClosedLoopEngine:
    """Join edge execution, RX SDR measurement, and software link delivery in one loop."""

    def __init__(self) -> None:
        self._edge = HardwareEdgeDeploymentEngine()
        self._sdr = PhysicalSdrIntegrationEngine()
        self._wireless = PhysicalWirelessLinkEngine()

    def run_synthetic(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: HardwareSdrClosedLoopConfig,
        timestamp_s: float,
        public_data: bool = False,
    ) -> HardwareSdrClosedLoopReport:
        return self._run(
            list(records),
            config=config,
            timestamp_s=timestamp_s,
            use_local_host=False,
            use_hardware_sdr=False,
            public_data=public_data,
        )

    def run_local_host(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: HardwareSdrClosedLoopConfig,
        timestamp_s: float,
        public_data: bool = False,
    ) -> HardwareSdrClosedLoopReport:
        return self._run(
            list(records),
            config=config,
            timestamp_s=timestamp_s,
            use_local_host=True,
            use_hardware_sdr=False,
            public_data=public_data,
        )

    def run_hardware_sdr(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: HardwareSdrClosedLoopConfig,
        timestamp_s: float,
        device_args: str = "",
        public_data: bool = False,
    ) -> HardwareSdrClosedLoopReport:
        return self._run(
            list(records),
            config=config,
            timestamp_s=timestamp_s,
            use_local_host=True,
            use_hardware_sdr=True,
            device_args=device_args,
            public_data=public_data,
        )

    def _run(
        self,
        records: list[TelemetryRecord],
        *,
        config: HardwareSdrClosedLoopConfig,
        timestamp_s: float,
        use_local_host: bool,
        use_hardware_sdr: bool,
        device_args: str = "",
        public_data: bool = False,
    ) -> HardwareSdrClosedLoopReport:
        edge_evidence = (
            HardwareEdgeEvidence.LOCAL_HOST_MEASUREMENT
            if use_local_host
            else HardwareEdgeEvidence.SYNTHETIC_FIXTURE
        )
        edge_device = local_host_profile() if use_local_host else synthetic_device_profile()
        edge_workload = EdgeWorkloadSpec(
            workload_id="phase72-telemetry-summary-v1",
            max_cpu_time_ms=50.0,
            max_python_heap_kb=512,
            max_wall_time_ms=100.0,
            maximum_input_records=max(128, len(records)),
        )
        edge_report = self._edge.deploy(
            records,
            device=edge_device,
            workload=edge_workload,
            evidence_class=edge_evidence,
        )

        sdr_config = PhysicalSdrConfig(
            device_args=device_args,
            channel=0,
            sample_rate_hz=config.sample_rate_hz,
            center_frequency_hz=config.center_frequency_hz,
            sample_count=config.sample_count,
            timeout_us=config.timeout_us,
        )
        if use_hardware_sdr:
            from sag_network.physical_sdr import SoapySdrRxBackend

            source = PhysicalSdrSource(SoapySdrRxBackend(device_args))
            sdr_evidence = PhysicalSdrEvidence.HARDWARE_MEASUREMENT
            top_evidence = HardwareSdrClosedLoopEvidence.HARDWARE_MEASUREMENT
        else:
            source = PhysicalSdrSource(SyntheticPhysicalSdrBackend(seed=7200))
            sdr_evidence = PhysicalSdrEvidence.SYNTHETIC_FIXTURE
            if use_local_host:
                top_evidence = HardwareSdrClosedLoopEvidence.LOCAL_HOST_MEASUREMENT
            elif public_data:
                top_evidence = HardwareSdrClosedLoopEvidence.PUBLIC_DATA
            else:
                top_evidence = HardwareSdrClosedLoopEvidence.SYNTHETIC_FIXTURE

        sdr_report = self._sdr.process(
            source=source,
            config=sdr_config,
            timestamp_s=timestamp_s,
            evidence_class=sdr_evidence,
        )

        control_payload = self._control_payload(edge_report, sdr_report)
        sha = hashlib.sha256(control_payload).hexdigest()
        link_config = PhysicalWirelessLinkConfig(
            source_id=config.source_id,
            destination_id=config.destination_id,
            payload=control_payload,
            sample_rate_hz=config.sample_rate_hz,
            symbol_rate_hz=config.symbol_rate_hz,
            amplitude=config.amplitude,
            decision_threshold=config.decision_threshold,
        )
        link_report = self._wireless.process_synthetic(
            config=link_config,
            timestamp_s=timestamp_s,
            evidence_class=PhysicalWirelessEvidence.SYNTHETIC_FIXTURE,
        )

        loop_payload: Mapping[str, object] = {
            "edge_output_fingerprint": edge_report.workload.output_fingerprint,
            "edge_summary": edge_report.telemetry_summary.model_dump(mode="json"),
            "sdr_sample_fingerprint": sdr_report.sample_fingerprint,
            "sdr_processing_fingerprint": sdr_report.processing_fingerprint,
            "wireless_link_fingerprint": link_report.link_fingerprint,
            "control_payload_sha256": sha,
            "evidence_class": top_evidence.value,
        }
        return HardwareSdrClosedLoopReport(
            evidence_class=top_evidence,
            edge=edge_report,
            sdr=sdr_report,
            wireless_link=link_report,
            control_payload_sha256=sha,
            loop_fingerprint=self._fingerprint(loop_payload),
            hardware_sdr_used=use_hardware_sdr,
            external_network_used=False,
            network_mutation=False,
        )

    @staticmethod
    def _control_payload(
        edge_report: HardwareEdgeDeploymentReport,
        sdr_report: PhysicalSdrReport,
    ) -> bytes:
        payload = {
            "workload_accepted": edge_report.workload.accepted,
            "input_record_count": edge_report.telemetry_summary.input_record_count,
            "mean_value": edge_report.telemetry_summary.mean_value,
            "rf_mean_power": sdr_report.mean_power,
            "rf_iq_imbalance_ratio": sdr_report.iq_imbalance_ratio,
            "rf_sample_count": sdr_report.sample_count,
        }
        return json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _fingerprint(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["HardwareSdrClosedLoopEngine"]
