from __future__ import annotations

import hashlib
import json
import time

from sag_network.decision.engine import DecisionEngine
from sag_network.decision.models import DecisionConfig, DecisionPriority
from sag_network.domain.unified import NetworkDomain
from sag_network.edge.coordinator import DistributedArchitectureEngine
from sag_network.edge.messaging import InMemoryMessageBroker
from sag_network.edge.models import (
    DistributedArchitectureConfig,
    EdgeCapability,
    EdgeFabricSnapshot,
    EdgeLink,
    EdgeNode,
    EdgeNodeHealth,
    EdgeNodeType,
)
from sag_network.edge.pipeline import build_pipeline_tasks
from sag_network.optimization.engine import AutonomousOptimizationEngine
from sag_network.optimization.models import OptimizationConfig
from sag_network.predictive.engine import PredictiveIntelligenceEngine
from sag_network.predictive.models import PredictiveConfig, PredictiveThresholdRule
from sag_network.recovery.engine import FailureRecoveryEngine
from sag_network.recovery.models import RecoveryConfig
from sag_network.telemetry.models import TelemetryMetric
from sag_network.telemetry.state import TelemetryStateStore
from sag_network.validation.models import (
    ValidationAggregateReport,
    ValidationRunMetrics,
    ValidationScenarioConfig,
    ValidationStatus,
)
from sag_network.validation.scenario import (
    build_network_snapshot,
    build_scenario,
    build_telemetry_records,
)


def default_validation_matrix() -> list[ValidationScenarioConfig]:
    """Return a deterministic scale matrix from smoke to stress workload."""
    return [
        ValidationScenarioConfig(scenario_id="scale-10", user_count=10),
        ValidationScenarioConfig(
            scenario_id="scale-50", user_count=50, interference_loss_db=2.0, fault_fraction=0.10
        ),
        ValidationScenarioConfig(
            scenario_id="scale-100",
            user_count=100,
            interference_loss_db=3.0,
            fault_fraction=0.10,
            traffic_multiplier=1.25,
        ),
        ValidationScenarioConfig(
            scenario_id="scale-250",
            user_count=250,
            interference_loss_db=4.0,
            fault_fraction=0.15,
            traffic_multiplier=1.5,
        ),
        ValidationScenarioConfig(
            scenario_id="scale-500",
            user_count=500,
            interference_loss_db=5.0,
            fault_fraction=0.15,
            traffic_multiplier=1.75,
        ),
    ]


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fabric(max_sources: int) -> EdgeFabricSnapshot:
    capabilities = list(EdgeCapability)
    nodes = [
        EdgeNode(
            node_id="ground-edge-a",
            node_type=EdgeNodeType.GROUND_EDGE,
            domain=NetworkDomain.GROUND,
            capabilities=capabilities,
            cpu_capacity_millicores=20_000,
            memory_capacity_mb=16_384,
            queue_capacity=max(100, max_sources * 7),
            processing_latency_ms=2.0,
            network_latency_ms=5.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
        EdgeNode(
            node_id="air-edge-a",
            node_type=EdgeNodeType.AIR_EDGE,
            domain=NetworkDomain.AIR,
            capabilities=capabilities,
            cpu_capacity_millicores=20_000,
            memory_capacity_mb=16_384,
            queue_capacity=max(100, max_sources * 7),
            processing_latency_ms=1.0,
            network_latency_ms=4.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
        EdgeNode(
            node_id="regional-a",
            node_type=EdgeNodeType.REGIONAL_CONTROLLER,
            capabilities=capabilities,
            cpu_capacity_millicores=30_000,
            memory_capacity_mb=32_768,
            queue_capacity=max(100, max_sources * 7),
            processing_latency_ms=3.0,
            network_latency_ms=7.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
        EdgeNode(
            node_id="central-a",
            node_type=EdgeNodeType.CENTRAL_CONTROLLER,
            capabilities=capabilities,
            cpu_capacity_millicores=40_000,
            memory_capacity_mb=65_536,
            queue_capacity=max(100, max_sources * 7),
            processing_latency_ms=5.0,
            network_latency_ms=15.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
    ]
    links = [
        EdgeLink(
            source_node_id="air-edge-a",
            target_node_id="regional-a",
            latency_ms=5.0,
            bandwidth_mbps=1000.0,
        ),
        EdgeLink(
            source_node_id="ground-edge-a",
            target_node_id="regional-a",
            latency_ms=7.0,
            bandwidth_mbps=1000.0,
        ),
        EdgeLink(
            source_node_id="regional-a",
            target_node_id="central-a",
            latency_ms=15.0,
            bandwidth_mbps=2000.0,
        ),
    ]
    return EdgeFabricSnapshot(timestamp_s=0.0, nodes=nodes, links=links)


def run_scenario(config: ValidationScenarioConfig) -> ValidationRunMetrics:
    """Execute one deterministic large-scale validation scenario."""
    start = time.perf_counter()
    scenario = build_scenario(config)
    network = build_network_snapshot(scenario)
    records = build_telemetry_records(scenario)

    telemetry_store = TelemetryStateStore()
    for record in records:
        telemetry_store.ingest(record, reference_time_s=config.timestamp_s)
    telemetry_state = telemetry_store.snapshot(timestamp_s=config.timestamp_s)

    predictive = PredictiveIntelligenceEngine(
        PredictiveConfig(horizon_steps=3, step_s=1.0, min_points=3, minimum_confidence=0.0)
    )
    rules = [
        PredictiveThresholdRule(
            metric=TelemetryMetric.SINR_DB,
            minimum_value=10.0,
            warning_within_s=5.0,
            critical_within_s=3.0,
            minimum_confidence=0.0,
        )
    ]
    predictive_report = predictive.analyze(
        records, reference_time_s=config.timestamp_s, rules=rules
    )

    decision = DecisionEngine(
        DecisionConfig(
            minimum_confidence=0.0,
            maximum_actions=max(1, config.user_count),
        )
    )
    decision_report = decision.decide(predictive_report, network_snapshot=network)

    optimization = AutonomousOptimizationEngine(
        OptimizationConfig(maximum_actions=max(1, config.user_count), minimum_expected_gain=0.0)
    )
    optimization_report = optimization.run(decision_report, network_snapshot=network)

    failed_network = build_network_snapshot(scenario, failed=True)
    recovery = FailureRecoveryEngine(
        RecoveryConfig(
            maximum_recovery_actions=max(1, len(scenario.fault_user_ids)),
            maximum_recovery_attempts=1,
        )
    )
    recovery_report = recovery.run(
        telemetry_state=telemetry_state,
        network_snapshot=failed_network,
        optimization_report=optimization_report,
        control_state=None,
    )

    source_count = min(config.edge_source_limit, max(1, config.user_count // 10))
    fabric = _fabric(source_count)
    distributed = DistributedArchitectureEngine(
        DistributedArchitectureConfig(maximum_tasks_per_cycle=source_count * 7)
    )
    tasks = [
        task
        for source_index in range(source_count)
        for task in build_pipeline_tasks(
            timestamp_s=config.timestamp_s,
            source_id=f"uav-a:user-{source_index + 1:04d}",
        )
    ]
    broker = InMemoryMessageBroker()
    message = InMemoryMessageBroker.create_message(
        source_node_id="air-edge-a",
        destination_node_id="regional-a",
        topic="validation.state",
        timestamp_s=config.timestamp_s,
        priority=DecisionPriority.HIGH,
        payload={"scenario_id": config.scenario_id, "user_count": config.user_count},
        ttl_s=5.0,
    )
    broker.publish(message)
    delivered = len(broker.consume("regional-a", now_s=config.timestamp_s + 1.0))
    distributed_report, _ = distributed.run_cycle(
        timestamp_s=config.timestamp_s,
        fabric=fabric.model_copy(update={"timestamp_s": config.timestamp_s}),
        tasks=tasks,
        state_payloads={
            "network": {"timestamp_s": config.timestamp_s, "scenario_id": config.scenario_id},
        },
        replica_node_ids=["regional-a", "central-a"],
    )

    placement_success = (
        distributed_report.results
    )
    placement_ratio = (
        sum(result.completed for result in placement_success) / len(tasks)
        if tasks
        else 1.0
    )
    recovered_count = sum(result.verified for result in recovery_report.execution_results)
    detected_count = len(recovery_report.detected_failures)
    recovery_ratio = recovered_count / detected_count if detected_count else 1.0

    logical_fingerprint = _fingerprint(
        {
            "scenario": config.model_dump(mode="json"),
            "warnings": predictive_report.model_dump(mode="json"),
            "decisions": decision_report.model_dump(mode="json"),
            "optimization": optimization_report.model_dump(mode="json"),
            "recovery": recovery_report.model_dump(mode="json"),
            "distributed": distributed_report.model_dump(mode="json"),
            "message_delivered": delivered,
        }
    )
    status = ValidationStatus.PASS
    if distributed_report.rejected_task_ids or not distributed.state_store.is_converged("network"):
        status = ValidationStatus.FAIL
    if detected_count and recovery_ratio < 1.0:
        status = ValidationStatus.FAIL
    runtime_ms = (time.perf_counter() - start) * 1000.0
    return ValidationRunMetrics(
        scenario_id=config.scenario_id,
        status=status,
        runtime_ms=runtime_ms,
        user_count=config.user_count,
        candidate_count=scenario.candidate_count,
        telemetry_records=len(records),
        predictive_warnings=len(predictive_report.early_warnings),
        selected_decisions=len(decision_report.selected_decisions),
        selected_control_actions=len(optimization_report.plan.selected_actions),
        detected_failures=detected_count,
        recovered_failures=recovered_count,
        distributed_tasks=len(tasks),
        completed_distributed_tasks=sum(result.completed for result in distributed_report.results),
        placement_success_ratio=placement_ratio,
        recovery_success_ratio=recovery_ratio,
        distributed_state_converged=distributed.state_store.is_converged("network"),
        message_delivered=delivered,
        deterministic_fingerprint=logical_fingerprint,
    )


def run_validation_matrix(
    configs: list[ValidationScenarioConfig] | None = None,
) -> ValidationAggregateReport:
    """Run the complete deterministic validation matrix and aggregate its metrics."""
    scenario_configs = configs or default_validation_matrix()
    runs = [run_scenario(config) for config in scenario_configs]
    aggregate_payload = [
        {key: value for key, value in item.model_dump(mode="json").items() if key != "runtime_ms"}
        for item in runs
    ]
    all_passed = all(item.status is ValidationStatus.PASS for item in runs)
    return ValidationAggregateReport(
        status=ValidationStatus.PASS if all_passed else ValidationStatus.FAIL,
        scenarios=runs,
        total_users=sum(item.user_count for item in runs),
        total_telemetry_records=sum(item.telemetry_records for item in runs),
        total_failures=sum(item.detected_failures for item in runs),
        total_recovered_failures=sum(item.recovered_failures for item in runs),
        minimum_recovery_success_ratio=min(item.recovery_success_ratio for item in runs),
        minimum_placement_success_ratio=min(item.placement_success_ratio for item in runs),
        all_distributed_state_converged=all(item.distributed_state_converged for item in runs),
        deterministic_matrix_fingerprint=_fingerprint(aggregate_payload),
    )


__all__ = ["default_validation_matrix", "run_scenario", "run_validation_matrix"]
