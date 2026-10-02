from __future__ import annotations

from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.telemetry.models import TelemetryMetric, TelemetryQuality, TelemetryRecord
from sag_network.validation.models import ValidationScenario, ValidationScenarioConfig

_RESOURCE_ORDER = ("gnd-a", "uav-a", "leo-a")
_DOMAIN_BY_RESOURCE = {
    "gnd-a": NetworkDomain.GROUND,
    "uav-a": NetworkDomain.AIR,
    "leo-a": NetworkDomain.SPACE,
}


def build_scenario(config: ValidationScenarioConfig) -> ValidationScenario:
    """Build deterministic benchmark identifiers and fault assignments."""
    user_ids = [f"user-{index:04d}" for index in range(1, config.user_count + 1)]
    fault_count = int(config.user_count * config.fault_fraction)
    fault_user_ids = user_ids[:fault_count]
    return ValidationScenario(
        config=config,
        user_ids=user_ids,
        candidate_count=config.user_count * len(_RESOURCE_ORDER),
        fault_user_ids=fault_user_ids,
    )


def _candidate(
    *,
    user_index: int,
    resource_id: str,
    config: ValidationScenarioConfig,
    available: bool = True,
) -> UnifiedCandidate:
    offset = user_index / 1000.0
    base = {
        "gnd-a": (9.0, 130_000_000.0, 15.0, 8.0, 7.0, 8.0),
        "uav-a": (16.0, 190_000_000.0, 9.0, 11.0, 9.0, 15.0),
        "leo-a": (12.0, 100_000_000.0, 45.0, 9.0, 8.0, 11.0),
    }[resource_id]
    margin_db, capacity_bps, delay_ms, rx_dbm, noise_dbm, sinr_db = base
    if resource_id == "uav-a":
        margin_db -= config.interference_loss_db
        capacity_bps = max(
            1_000_000.0,
            capacity_bps * (10 ** (-config.interference_loss_db / 10.0)),
        )
        sinr_db -= config.interference_loss_db
        rx_dbm -= config.interference_loss_db
    return UnifiedCandidate(
        resource_id=resource_id,
        domain=_DOMAIN_BY_RESOURCE[resource_id],
        resource_type=resource_id.split("-", maxsplit=1)[0],
        available=available,
        distance_m=(20_000.0 + user_index * 10.0) if resource_id == "uav-a" else 50_000.0,
        rx_power_dbm=rx_dbm + offset,
        noise_power_dbm=noise_dbm,
        sinr_db=sinr_db + offset,
        link_margin_db=max(0.1, margin_db + offset),
        shannon_capacity_bps=capacity_bps,
        estimated_capacity_bps=capacity_bps,
        propagation_delay_ms=delay_ms,
        doppler_shift_hz=0.0 if resource_id != "gnd-a" else None,
        remaining_energy_wh=(900.0 - user_index * 0.1) if resource_id == "uav-a" else None,
    )


def build_network_snapshot(
    scenario: ValidationScenario,
    *,
    failed: bool = False,
) -> UnifiedNetworkSnapshot:
    """Build a deterministic network snapshot for a healthy or fault-injected state."""
    fault_users = set(scenario.fault_user_ids) if failed else set()
    associations: list[UnifiedUserAssociation] = []
    for index, user_id in enumerate(scenario.user_ids, start=1):
        candidates = [
            _candidate(
                user_index=index,
                resource_id=resource_id,
                config=scenario.config,
                available=not (resource_id == "uav-a" and user_id in fault_users),
            )
            for resource_id in _RESOURCE_ORDER
        ]
        demand_bps = 20_000_000.0 * scenario.config.traffic_multiplier
        selected = "uav-a"
        selected_candidate = next(item for item in candidates if item.resource_id == selected)
        associations.append(
            UnifiedUserAssociation(
                user_id=user_id,
                selected_resource_id=selected,
                selected_domain=selected_candidate.domain,
                demand_bps=demand_bps,
                allocated_capacity_bps=min(demand_bps, selected_candidate.estimated_capacity_bps),
                candidates=candidates,
            )
        )
    return UnifiedNetworkSnapshot(
        timestamp_s=scenario.config.timestamp_s,
        associations=associations,
    )


def build_telemetry_records(scenario: ValidationScenario) -> list[TelemetryRecord]:
    """Build deterministic SINR histories that exercise the predictive baseline."""
    records: list[TelemetryRecord] = []
    for user_index, user_id in enumerate(scenario.user_ids, start=1):
        source_id = f"uav-a:{user_id}"
        latest_time = scenario.config.timestamp_s
        for sequence in range(scenario.config.telemetry_points):
            timestamp_s = latest_time - float(scenario.config.telemetry_points - 1 - sequence)
            latest_value = 12.0 + (user_index % 5) * 0.1
            value = latest_value + (scenario.config.telemetry_points - 1 - sequence) * 2.0
            record_id = f"{source_id}:sinr:{sequence}"
            records.append(
                TelemetryRecord(
                    record_id=record_id,
                    timestamp_s=timestamp_s,
                    sequence=sequence,
                    source_id=source_id,
                    domain=NetworkDomain.AIR,
                    metric=TelemetryMetric.SINR_DB,
                    value=value,
                    unit="dB",
                    quality=TelemetryQuality.GOOD,
                    metadata={"scenario": scenario.config.scenario_id},
                )
            )
    return records


__all__ = ["build_network_snapshot", "build_scenario", "build_telemetry_records"]
