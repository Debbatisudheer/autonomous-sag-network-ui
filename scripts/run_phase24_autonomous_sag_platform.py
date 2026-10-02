from __future__ import annotations

import json

from sag_network.domain.unified import NetworkDomain
from sag_network.edge.models import (
    EdgeCapability,
    EdgeFabricSnapshot,
    EdgeLink,
    EdgeNode,
    EdgeNodeHealth,
    EdgeNodeType,
)
from sag_network.platform.engine import AutonomousSAGPlatform
from sag_network.platform.models import AutonomousPlatformConfig, PlatformCycleInput
from sag_network.validation.models import ValidationScenarioConfig
from sag_network.validation.scenario import (
    build_network_snapshot,
    build_scenario,
    build_telemetry_records,
)


def fabric(timestamp_s: float) -> EdgeFabricSnapshot:
    capabilities = list(EdgeCapability)
    nodes = [
        EdgeNode(
            node_id="air-edge-a",
            node_type=EdgeNodeType.AIR_EDGE,
            domain=NetworkDomain.AIR,
            capabilities=capabilities,
            cpu_capacity_millicores=20000,
            memory_capacity_mb=16384,
            queue_capacity=100,
            processing_latency_ms=1.0,
            network_latency_ms=4.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
        EdgeNode(
            node_id="ground-edge-a",
            node_type=EdgeNodeType.GROUND_EDGE,
            domain=NetworkDomain.GROUND,
            capabilities=capabilities,
            cpu_capacity_millicores=20000,
            memory_capacity_mb=16384,
            queue_capacity=100,
            processing_latency_ms=1.0,
            network_latency_ms=5.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
        EdgeNode(
            node_id="regional-controller",
            node_type=EdgeNodeType.REGIONAL_CONTROLLER,
            capabilities=capabilities,
            cpu_capacity_millicores=30000,
            memory_capacity_mb=32768,
            queue_capacity=200,
            processing_latency_ms=3.0,
            network_latency_ms=7.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
        EdgeNode(
            node_id="central-controller",
            node_type=EdgeNodeType.CENTRAL_CONTROLLER,
            capabilities=capabilities,
            cpu_capacity_millicores=40000,
            memory_capacity_mb=65536,
            queue_capacity=200,
            processing_latency_ms=5.0,
            network_latency_ms=15.0,
            health=EdgeNodeHealth.ONLINE,
            active=True,
        ),
    ]
    links = [
        EdgeLink(
            source_node_id="air-edge-a",
            target_node_id="regional-controller",
            latency_ms=5.0,
            bandwidth_mbps=1000.0,
        ),
        EdgeLink(
            source_node_id="ground-edge-a",
            target_node_id="regional-controller",
            latency_ms=7.0,
            bandwidth_mbps=1000.0,
        ),
        EdgeLink(
            source_node_id="regional-controller",
            target_node_id="central-controller",
            latency_ms=15.0,
            bandwidth_mbps=2000.0,
        ),
    ]
    return EdgeFabricSnapshot(timestamp_s=timestamp_s, nodes=nodes, links=links)


def main() -> None:
    config = ValidationScenarioConfig(
        scenario_id="platform-final",
        user_count=10,
        fault_fraction=0.2,
        timestamp_s=40.0,
        telemetry_points=4,
        edge_source_limit=10,
    )
    scenario = build_scenario(config)
    network = build_network_snapshot(scenario)
    failed_network = build_network_snapshot(scenario, failed=True)
    records = build_telemetry_records(scenario)
    platform = AutonomousSAGPlatform(
        AutonomousPlatformConfig(
            platform_id="sag-platform-final",
            network_name="autonomous-sag-network",
        )
    )
    report = platform.run_cycle(
        PlatformCycleInput(
            timestamp_s=config.timestamp_s,
            network_snapshot=network,
            failure_network_snapshot=failed_network,
            telemetry_records=records,
            edge_fabric=fabric(config.timestamp_s),
            source_ids=(
                [f"uav-a:{user_id}" for user_id in scenario.fault_user_ids]
                or ["uav-a:user-0001"]
            ),
        )
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
