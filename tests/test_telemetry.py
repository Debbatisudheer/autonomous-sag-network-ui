from __future__ import annotations

import pytest

from sag_network.digital_twin import DigitalTwin, DigitalTwinConfig
from sag_network.domain.resource import ResourceUtilization, SpectrumSchedulingSnapshot
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.interference.model import InterferenceEvaluation
from sag_network.telemetry import (
    TelemetryBatch,
    TelemetryDigitalTwinBridge,
    TelemetryIngestionConfig,
    TelemetryMetric,
    TelemetryRecord,
    TelemetryStateStore,
)
from sag_network.telemetry.generator import (
    generate_interference_telemetry,
    generate_spectrum_telemetry,
    generate_unified_telemetry,
)


def candidate(*, resource_id: str = "uav-a", sinr_db: float = 20.0) -> UnifiedCandidate:
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=NetworkDomain.AIR,
        resource_type="uav",
        available=True,
        distance_m=10_000.0,
        rx_power_dbm=-65.0,
        noise_power_dbm=-95.0,
        sinr_db=sinr_db,
        link_margin_db=sinr_db - 5.0,
        shannon_capacity_bps=150_000_000.0,
        estimated_capacity_bps=100_000_000.0,
        propagation_delay_ms=0.1,
        doppler_shift_hz=125.0,
        remaining_energy_wh=80.0,
    )


def unified_snapshot(timestamp_s: float) -> UnifiedNetworkSnapshot:
    return UnifiedNetworkSnapshot(
        timestamp_s=timestamp_s,
        associations=[
            UnifiedUserAssociation(
                user_id="user-01",
                selected_resource_id="uav-a",
                selected_domain=NetworkDomain.AIR,
                demand_bps=50_000_000.0,
                allocated_capacity_bps=100_000_000.0,
                candidates=[candidate()],
            )
        ],
    )


def record(
    *,
    record_id: str = "r-01",
    timestamp_s: float = 10.0,
    sequence: int = 1,
    source_id: str = "uav-a:user-01",
    value: float = 20.0,
    metric: TelemetryMetric = TelemetryMetric.SINR_DB,
) -> TelemetryRecord:
    return TelemetryRecord(
        record_id=record_id,
        timestamp_s=timestamp_s,
        sequence=sequence,
        source_id=source_id,
        domain=NetworkDomain.AIR,
        metric=metric,
        value=value,
        unit="dB",
    )


def test_unified_generator_is_deterministic_and_uses_existing_measurements() -> None:
    snapshot = unified_snapshot(10.0)
    first = generate_unified_telemetry(snapshot, sequence_start=0)
    second = generate_unified_telemetry(snapshot, sequence_start=0)
    assert first == second
    sinr_records = [item for item in first.records if item.metric is TelemetryMetric.SINR_DB]
    assert len(sinr_records) == 1
    assert sinr_records[0].value == 20.0
    assert sinr_records[0].metadata == {"user_id": "user-01"}


def test_unified_generator_includes_optional_doppler_and_energy() -> None:
    batch = generate_unified_telemetry(unified_snapshot(10.0))
    metrics = {record.metric for record in batch.records}
    assert TelemetryMetric.DOPPLER_SHIFT_HZ in metrics
    assert TelemetryMetric.REMAINING_ENERGY_WH in metrics


def test_store_accepts_latest_record_and_materializes_state() -> None:
    store = TelemetryStateStore()
    result = store.ingest(record(), reference_time_s=10.0)
    assert result.accepted_count == 1
    state = store.snapshot(timestamp_s=10.5)
    assert state.sample_count == 1
    assert state.stale_sample_count == 0
    assert state.samples[0].age_s == pytest.approx(0.5)
    assert state.samples[0].stale is False


def test_store_rejects_duplicate_record_id() -> None:
    store = TelemetryStateStore()
    first = record()
    store.ingest(first, reference_time_s=10.0)
    second = record(record_id="r-02", sequence=2)
    store.ingest(second, reference_time_s=10.0)
    duplicate = store.ingest(first, reference_time_s=10.0)
    assert duplicate.rejected_count == 1
    assert "already been accepted" in duplicate.rejected_records[0].reason


def test_store_rejects_old_sequence() -> None:
    store = TelemetryStateStore()
    store.ingest(record(sequence=5, record_id="r-05"), reference_time_s=10.0)
    result = store.ingest(record(sequence=4, record_id="r-04"), reference_time_s=10.0)
    assert result.rejected_count == 1
    assert "older than latest" in result.rejected_records[0].reason


def test_store_rejects_equal_sequence() -> None:
    store = TelemetryStateStore()
    store.ingest(record(sequence=5, record_id="r-05"), reference_time_s=10.0)
    result = store.ingest(record(sequence=5, record_id="r-05b"), reference_time_s=10.0)
    assert result.rejected_count == 1
    assert "duplicates latest" in result.rejected_records[0].reason


def test_store_rejects_future_record() -> None:
    store = TelemetryStateStore()
    result = store.ingest(record(timestamp_s=11.0), reference_time_s=10.0)
    assert result.rejected_count == 1
    assert "future skew" in result.rejected_records[0].reason


def test_future_skew_can_be_explicitly_allowed() -> None:
    store = TelemetryStateStore(
        TelemetryIngestionConfig(max_future_skew_s=1.0)
    )
    result = store.ingest(record(timestamp_s=11.0), reference_time_s=10.0)
    assert result.accepted_count == 1


def test_stale_state_is_marked_without_mutating_latest_value() -> None:
    store = TelemetryStateStore(TelemetryIngestionConfig(stale_after_s=2.0))
    store.ingest(record(timestamp_s=10.0), reference_time_s=10.0)
    state = store.snapshot(timestamp_s=12.1)
    assert state.samples[0].stale is True
    assert store.latest_for(source_id="uav-a:user-01", metric="sinr_db") is not None


def test_batch_ingestion_preserves_input_order() -> None:
    store = TelemetryStateStore()
    records = [record(record_id=f"r-{i}", sequence=i) for i in range(3)]
    result = store.ingest_batch(
        TelemetryBatch(batch_id="batch-01", timestamp_s=10.0, records=records),
        reference_time_s=10.0,
    )
    assert result.accepted_record_ids == ["r-0", "r-1", "r-2"]
    assert result.state_updates == 3


def test_history_limit_retains_recent_records_only() -> None:
    store = TelemetryStateStore(TelemetryIngestionConfig(history_limit=2))
    for index in range(3):
        store.ingest(
            record(record_id=f"r-{index}", sequence=index, timestamp_s=float(index)),
            reference_time_s=float(index),
        )
    assert [item.record_id for item in store.history] == ["r-1", "r-2"]


def test_snapshot_sorts_latest_state_deterministically() -> None:
    store = TelemetryStateStore()
    store.ingest(
        record(record_id="r-sinr", sequence=1, metric=TelemetryMetric.SINR_DB),
        reference_time_s=10.0,
    )
    store.ingest(
        record(
            record_id="r-pwr",
            sequence=2,
            source_id="gnd-a:user-01",
            metric=TelemetryMetric.RECEIVED_POWER_DBM,
            value=-70.0,
        ),
        reference_time_s=10.0,
    )
    state = store.snapshot(timestamp_s=10.0)
    assert [(item.source_id, item.metric.value) for item in state.samples] == [
        ("gnd-a:user-01", "received_power_dbm"),
        ("uav-a:user-01", "sinr_db"),
    ]


def test_spectrum_generator_emits_utilization_and_capacity_metrics() -> None:
    snapshot = SpectrumSchedulingSnapshot(
        timestamp_s=10.0,
        allocations=[],
        utilization=[
            ResourceUtilization(
                resource_id="uav-a",
                total_resource_blocks=20,
                used_resource_blocks=8,
                free_resource_blocks=12,
                utilization_ratio=0.4,
                scheduled_capacity_bps=80_000_000.0,
                remaining_capacity_bps=120_000_000.0,
            )
        ],
    )
    batch = generate_spectrum_telemetry(
        snapshot,
        resource_domains={"uav-a": NetworkDomain.AIR},
    )
    assert {record.metric for record in batch.records} == {
        TelemetryMetric.RESOURCE_UTILIZATION_RATIO,
        TelemetryMetric.RESOURCE_SCHEDULED_CAPACITY_BPS,
        TelemetryMetric.RESOURCE_REMAINING_CAPACITY_BPS,
    }


def test_store_rejects_timestamp_regression_even_with_newer_sequence() -> None:
    store = TelemetryStateStore()
    store.ingest(record(record_id="r-10", sequence=10, timestamp_s=10.0), reference_time_s=10.0)
    result = store.ingest(record(record_id="r-11", sequence=11, timestamp_s=9.0), reference_time_s=10.0)
    assert result.rejected_count == 1
    assert "timestamp is older" in result.rejected_records[0].reason


def test_timestamp_regression_can_be_disabled_independently() -> None:
    store = TelemetryStateStore(
        TelemetryIngestionConfig(enforce_monotonic_timestamp=False)
    )
    store.ingest(record(record_id="r-10", sequence=10, timestamp_s=10.0), reference_time_s=10.0)
    result = store.ingest(record(record_id="r-11", sequence=11, timestamp_s=9.0), reference_time_s=10.0)
    assert result.accepted_count == 1


def test_interference_metric_has_explicit_identity() -> None:
    evaluation = InterferenceEvaluation(
        desired_rx_power_dbm=-70.0,
        noise_power_dbm=-100.0,
        aggregate_interference_power_dbm=-80.0,
        sinr_db=8.0,
        shannon_capacity_bps=50_000_000.0,
        interference_degradation_db=12.0,
        contributions=[],
    )
    batch = generate_interference_telemetry(
        [evaluation],
        timestamp_s=20.0,
        resource_ids=["uav-a"],
        domain=NetworkDomain.AIR,
    )
    assert batch.records[0].metric is TelemetryMetric.INTERFERENCE_POWER_DBM
    assert batch.records[0].source_id == "uav-a"


def test_digital_twin_bridge_requires_exact_time_alignment() -> None:
    unified = unified_snapshot(10.0)
    twin = DigitalTwin(DigitalTwinConfig(twin_id="twin-01", network_name="sag-demo"))
    twin_snapshot = twin.create_snapshot(
        snapshot_id="snapshot-01",
        timestamp_s=10.0,
        network_name="sag-demo",
        unified_state=unified,
    )
    store = TelemetryStateStore()
    store.ingest(record(timestamp_s=10.0), reference_time_s=10.0)
    state = store.snapshot(timestamp_s=10.0)
    link = TelemetryDigitalTwinBridge.link(telemetry_state=state, twin_snapshot=twin_snapshot)
    assert link.twin_snapshot_id == "snapshot-01"
    assert link.sample_count == 1


def test_digital_twin_bridge_rejects_misaligned_time() -> None:
    unified = unified_snapshot(10.0)
    twin = DigitalTwin(DigitalTwinConfig(twin_id="twin-01", network_name="sag-demo"))
    twin_snapshot = twin.create_snapshot(
        snapshot_id="snapshot-01",
        timestamp_s=10.0,
        network_name="sag-demo",
        unified_state=unified,
    )
    store = TelemetryStateStore()
    store.ingest(record(timestamp_s=10.0), reference_time_s=10.0)
    state = store.snapshot(timestamp_s=11.0)
    with pytest.raises(ValueError, match="timestamp"):
        TelemetryDigitalTwinBridge.link(telemetry_state=state, twin_snapshot=twin_snapshot)
