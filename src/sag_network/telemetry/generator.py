from __future__ import annotations

from collections.abc import Iterable, Mapping

from sag_network.domain.resource import SpectrumSchedulingSnapshot
from sag_network.domain.unified import NetworkDomain, UnifiedNetworkSnapshot
from sag_network.interference.model import InterferenceEvaluation
from sag_network.telemetry.models import TelemetryBatch, TelemetryMetric, TelemetryRecord


def _record(
    *,
    record_id: str,
    timestamp_s: float,
    sequence: int,
    source_id: str,
    domain: NetworkDomain,
    metric: TelemetryMetric,
    value: float,
    unit: str,
    metadata: dict[str, str] | None = None,
) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=sequence,
        source_id=source_id,
        domain=domain,
        metric=metric,
        value=value,
        unit=unit,
        metadata=metadata or {},
    )


def generate_unified_telemetry(
    snapshot: UnifiedNetworkSnapshot,
    *,
    sequence_start: int = 0,
) -> TelemetryBatch:
    """Generate deterministic link telemetry directly from validated unified observations."""
    records: list[TelemetryRecord] = []
    sequence = sequence_start
    timestamp_s = snapshot.timestamp_s
    for association in snapshot.associations:
        for candidate in association.candidates:
            source_id = f"{candidate.resource_id}:{association.user_id}"
            prefix = f"{source_id}:{timestamp_s:.6f}"
            metrics = [
                (TelemetryMetric.AVAILABLE, 1.0 if candidate.available else 0.0, "bool"),
                (TelemetryMetric.RECEIVED_POWER_DBM, candidate.rx_power_dbm, "dBm"),
                (TelemetryMetric.NOISE_POWER_DBM, candidate.noise_power_dbm, "dBm"),
                (TelemetryMetric.SINR_DB, candidate.sinr_db, "dB"),
                (TelemetryMetric.LINK_MARGIN_DB, candidate.link_margin_db, "dB"),
                (TelemetryMetric.CAPACITY_BPS, candidate.shannon_capacity_bps, "bit/s"),
                (TelemetryMetric.LATENCY_MS, candidate.propagation_delay_ms, "ms"),
            ]
            if candidate.doppler_shift_hz is not None:
                metrics.append(
                    (TelemetryMetric.DOPPLER_SHIFT_HZ, candidate.doppler_shift_hz, "Hz")
                )
            if candidate.remaining_energy_wh is not None:
                metrics.append(
                    (TelemetryMetric.REMAINING_ENERGY_WH, candidate.remaining_energy_wh, "Wh")
                )
            for metric, value, unit in metrics:
                records.append(
                    _record(
                        record_id=f"{prefix}:{metric.value}",
                        timestamp_s=timestamp_s,
                        sequence=sequence,
                        source_id=source_id,
                        domain=candidate.domain,
                        metric=metric,
                        value=value,
                        unit=unit,
                        metadata={"user_id": association.user_id},
                    )
                )
                sequence += 1
    return TelemetryBatch(
        batch_id=f"unified:{timestamp_s:.6f}",
        timestamp_s=timestamp_s,
        records=records,
        source="unified-network",
    )


def generate_spectrum_telemetry(
    snapshot: SpectrumSchedulingSnapshot,
    *,
    resource_domains: Mapping[str, NetworkDomain],
    sequence_start: int = 0,
) -> TelemetryBatch:
    """Generate deterministic resource utilization telemetry."""
    records: list[TelemetryRecord] = []
    sequence = sequence_start
    for utilization in snapshot.utilization:
        source_id = utilization.resource_id
        for metric, value, unit in (
            (
                TelemetryMetric.RESOURCE_UTILIZATION_RATIO,
                utilization.utilization_ratio,
                "ratio",
            ),
            (
                TelemetryMetric.RESOURCE_SCHEDULED_CAPACITY_BPS,
                utilization.scheduled_capacity_bps,
                "bit/s",
            ),
            (
                TelemetryMetric.RESOURCE_REMAINING_CAPACITY_BPS,
                utilization.remaining_capacity_bps,
                "bit/s",
            ),
        ):
            records.append(
                _record(
                    record_id=f"spectrum:{snapshot.timestamp_s:.6f}:{source_id}:{metric.value}",
                    timestamp_s=snapshot.timestamp_s,
                    sequence=sequence,
                    source_id=source_id,
                    domain=resource_domains[source_id],
                    metric=metric,
                    value=value,
                    unit=unit,
                )
            )
            sequence += 1
    return TelemetryBatch(
        batch_id=f"spectrum:{snapshot.timestamp_s:.6f}",
        timestamp_s=snapshot.timestamp_s,
        records=records,
        source="spectrum-scheduler",
    )


def generate_interference_telemetry(
    evaluations: Iterable[InterferenceEvaluation],
    *,
    timestamp_s: float,
    sequence_start: int = 0,
    resource_ids: Iterable[str] | None = None,
    domain: NetworkDomain = NetworkDomain.AIR,
) -> TelemetryBatch:
    """Generate deterministic aggregate interference telemetry from Phase 14 evaluations."""
    records: list[TelemetryRecord] = []
    sequence = sequence_start
    resource_id_iter = iter(resource_ids) if resource_ids is not None else None
    for index, evaluation in enumerate(evaluations):
        resource_id = next(resource_id_iter, None) if resource_id_iter is not None else None
        source_id = resource_id or f"interference-evaluation-{index}"
        if evaluation.aggregate_interference_power_dbm is not None:
            records.append(
                _record(
                    record_id=(
                        f"interference:{timestamp_s:.6f}:{index}:aggregate_power_dbm"
                    ),
                    timestamp_s=timestamp_s,
                    sequence=sequence,
                    source_id=source_id,
                    domain=domain,
                    metric=TelemetryMetric.INTERFERENCE_POWER_DBM,
                    value=evaluation.aggregate_interference_power_dbm,
                    unit="dBm",
                    metadata={"evaluation_index": str(index)},
                )
            )
            sequence += 1
    return TelemetryBatch(
        batch_id=f"interference:{timestamp_s:.6f}",
        timestamp_s=timestamp_s,
        records=records,
        source="interference-evaluator",
    )
