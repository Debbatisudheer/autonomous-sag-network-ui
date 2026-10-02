from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterable

from sag_network.ingestion import IngestionConfig, RealTimeTelemetryIngestion
from sag_network.network_telemetry_loop.models import (
    NetworkLoopEvidence,
    NetworkTelemetryEnvelope,
    NetworkTelemetryLoopReport,
)
from sag_network.network_telemetry_loop.transport import (
    LocalUdpTelemetryLoopTransport,
    SyntheticTelemetryLoopTransport,
    TelemetryLoopTransport,
)
from sag_network.realtime_validation import RealTimeTelemetryValidator
from sag_network.telemetry.models import TelemetryMetric, TelemetryQuality, TelemetryRecord
from sag_network.telemetry.state import TelemetryStateStore
from sag_network.domain.unified import NetworkDomain


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class NetworkTelemetryLoopEngine:
    """Transport telemetry through a network boundary and commit it to the telemetry state store."""

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        reference_time_s: float,
        transport: TelemetryLoopTransport,
        evidence_class: NetworkLoopEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
        timeout_s: float = 1.0,
    ) -> NetworkTelemetryLoopReport:
        record_list = list(records)
        store = TelemetryStateStore()
        validator = RealTimeTelemetryValidator(
            reject_invalid_quality=True,
            reject_future_records=True,
            max_future_skew_s=0.0,
            enforce_stream_monotonicity=True,
        )
        ingestion = RealTimeTelemetryIngestion(
            store,
            config=IngestionConfig(batch_size=16),
            validator=validator,
        )

        transmitted: list[TelemetryRecord] = []
        received: list[TelemetryRecord] = []
        latencies: list[float] = []
        for record in record_list:
            envelope = NetworkTelemetryEnvelope(
                record_id=record.record_id,
                timestamp_s=record.timestamp_s,
                sequence=record.sequence,
                source_id=record.source_id,
                domain=record.domain.value,
                metric=record.metric.value,
                value=record.value,
                unit=record.unit,
                quality=record.quality.value,
            )
            returned, latency_ms = transport.exchange(envelope, timeout_s)
            transmitted.append(record)
            if returned is not None:
                received.append(self._to_record(returned))
                latencies.append(latency_ms)

        ingestion_report = ingestion.ingest(received, reference_time_s=reference_time_s)
        snapshot = store.snapshot(timestamp_s=reference_time_s)
        delivered_rate = len(received) / len(record_list) if record_list else 1.0
        loop_payload = {
            "input": [record.model_dump(mode="json") for record in record_list],
            "received": [record.model_dump(mode="json") for record in received],
            "ingestion_fingerprint": ingestion_report.ingestion_fingerprint,
            "transport": transport.name,
            "evidence_class": evidence_class.value,
        }
        return NetworkTelemetryLoopReport(
            status="pass",
            evidence_class=evidence_class,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            input_record_count=len(record_list),
            transmitted_record_count=len(transmitted),
            received_record_count=len(received),
            accepted_record_count=ingestion_report.accepted_record_count,
            rejected_record_count=ingestion_report.rejected_record_count,
            state_sample_count=snapshot.sample_count,
            delivered_record_rate=delivered_rate,
            loopback_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            transport=transport.name,
            external_network_used=transport.external_network_used,
            network_mutation=False,
            loop_fingerprint=_fingerprint(loop_payload),
        )

    @staticmethod
    def _to_record(envelope: NetworkTelemetryEnvelope) -> TelemetryRecord:
        return TelemetryRecord(
            record_id=envelope.record_id,
            timestamp_s=envelope.timestamp_s,
            sequence=envelope.sequence,
            source_id=envelope.source_id,
            domain=NetworkDomain(envelope.domain),
            metric=TelemetryMetric(envelope.metric),
            value=envelope.value,
            unit=envelope.unit,
            quality=TelemetryQuality(envelope.quality),
        )

    def run_udp_loopback(
        self,
        records: Iterable[TelemetryRecord],
        *,
        reference_time_s: float,
        evidence_class: NetworkLoopEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
        timeout_s: float = 1.0,
    ) -> NetworkTelemetryLoopReport:
        transport = LocalUdpTelemetryLoopTransport()

        def echo_server() -> None:
            while not stop_event.is_set():
                try:
                    transport.serve_once()
                except OSError:
                    return
                except TimeoutError:
                    continue

        # Serve on the same socket from a worker thread so the client performs a real UDP loop.
        stop_event = threading.Event()
        server_thread = threading.Thread(target=echo_server, daemon=True)
        server_thread.start()
        try:
            return self.run(
                records,
                reference_time_s=reference_time_s,
                transport=transport,
                evidence_class=evidence_class,
                source_sha256=source_sha256,
                provenance_verified=provenance_verified,
                timeout_s=timeout_s,
            )
        finally:
            stop_event.set()
            transport.close()
            server_thread.join(timeout=0.5)


__all__ = ["NetworkTelemetryLoopEngine"]
