from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from sag_network.air.association import evaluate_air_network
from sag_network.domain.air import AirNetwork, AirNetworkSnapshot, AirPlatform, AirPlatformType
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.air_segment.models import (
    AirSegmentConfig,
    AirSegmentEvidence,
    AirSegmentIntegrationReport,
    AirSegmentSummary,
)
from sag_network.network_telemetry_loop import NetworkLoopEvidence, NetworkTelemetryLoopEngine
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport
from sag_network.network_telemetry_loop.transport import SyntheticTelemetryLoopTransport
from sag_network.telemetry.models import TelemetryRecord


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_air_network() -> AirNetwork:
    """Return a deterministic UAV + HAPS network for Phase 74 integration."""
    propagation_uav = PropagationLosses(
        atmospheric_db=1.0,
        rain_db=1.0,
        polarization_db=1.0,
        implementation_db=2.0,
    )
    propagation_haps = PropagationLosses(
        atmospheric_db=2.0,
        rain_db=2.0,
        polarization_db=1.0,
        implementation_db=2.0,
    )
    return AirNetwork(
        name="phase74-air-segment",
        platforms=[
            AirPlatform(
                platform_id="air-uav-01",
                platform_type=AirPlatformType.UAV,
                initial_position=GeoPoint(
                    latitude_deg=17.3850,
                    longitude_deg=78.4867,
                    altitude_m=1_000.0,
                ),
                mobility=MobilityProfile(
                    north_velocity_mps=10.0,
                    east_velocity_mps=5.0,
                ),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=33.0,
                tx_gain_dbi=10.0,
                rx_gain_dbi=8.0,
                noise_figure_db=5.0,
                required_sinr_db=8.0,
                maximum_service_distance_m=25_000.0,
                propagation_losses=propagation_uav,
                scheduler_efficiency=0.75,
                initial_energy_wh=100.0,
                reserve_energy_wh=20.0,
                hotel_power_w=40.0,
                propulsion_power_w=80.0,
            ),
            AirPlatform(
                platform_id="air-haps-01",
                platform_type=AirPlatformType.HAPS,
                initial_position=GeoPoint(
                    latitude_deg=17.4050,
                    longitude_deg=78.4900,
                    altitude_m=20_000.0,
                ),
                mobility=MobilityProfile(),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=40.0,
                tx_gain_dbi=16.0,
                rx_gain_dbi=10.0,
                noise_figure_db=5.0,
                required_sinr_db=8.0,
                maximum_service_distance_m=100_000.0,
                propagation_losses=propagation_haps,
                scheduler_efficiency=0.75,
                initial_energy_wh=5_000.0,
                reserve_energy_wh=500.0,
                hotel_power_w=500.0,
                propulsion_power_w=0.0,
            ),
        ],
    )


def default_air_users() -> list[MobileUser]:
    """Return deterministic moving users in the Hyderabad-area fixture."""
    return [
        MobileUser(
            user_id="air-user-01",
            initial_position=GeoPoint(
                latitude_deg=17.3850,
                longitude_deg=78.4867,
                altitude_m=540.0,
            ),
            mobility=MobilityProfile(
                north_velocity_mps=5.0,
                east_velocity_mps=2.0,
            ),
        ),
        MobileUser(
            user_id="air-user-02",
            initial_position=GeoPoint(
                latitude_deg=17.4000,
                longitude_deg=78.4920,
                altitude_m=540.0,
            ),
            mobility=MobilityProfile(
                north_velocity_mps=-2.0,
                east_velocity_mps=4.0,
            ),
        ),
        MobileUser(
            user_id="air-user-03",
            initial_position=GeoPoint(
                latitude_deg=17.3950,
                longitude_deg=78.4750,
                altitude_m=540.0,
            ),
            mobility=MobilityProfile(
                north_velocity_mps=1.0,
                east_velocity_mps=-3.0,
            ),
        ),
    ]


class AirSegmentIntegrationEngine:
    """Integrate canonical telemetry state with the existing airborne network model."""

    def __init__(self) -> None:
        self._telemetry = NetworkTelemetryLoopEngine()

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: AirSegmentConfig,
        evidence_class: AirSegmentEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> AirSegmentIntegrationReport:
        record_list = list(records)
        reference_time_s = config.reference_time_s
        if record_list:
            reference_time_s = max(
                reference_time_s,
                max(record.timestamp_s for record in record_list),
            )

        loop_evidence = self._loop_evidence(
            evidence_class,
            config.use_udp_loopback,
        )
        if config.use_udp_loopback:
            telemetry_report = self._telemetry.run_udp_loopback(
                record_list,
                reference_time_s=reference_time_s,
                evidence_class=loop_evidence,
                source_sha256=source_sha256,
                provenance_verified=provenance_verified,
                timeout_s=config.timeout_s,
            )
        else:
            telemetry_report = self._telemetry.run(
                record_list,
                reference_time_s=reference_time_s,
                transport=SyntheticTelemetryLoopTransport(),
                evidence_class=loop_evidence,
                source_sha256=source_sha256,
                provenance_verified=provenance_verified,
                timeout_s=config.timeout_s,
            )

        network = default_air_network()
        users = default_air_users()
        demands = {
            user.user_id: config.user_demand_bps.get(user.user_id, 10e6)
            for user in users
        }
        air_snapshot = evaluate_air_network(
            network=network,
            users=users,
            demands_bps=demands,
            timestamp_s=reference_time_s,
        )
        summary = self._summary(
            air_snapshot,
            network,
            telemetry_report,
            record_list,
            reference_time_s,
        )
        payload = {
            "telemetry_loop": telemetry_report.model_dump(mode="json"),
            "air_snapshot": air_snapshot.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
        }
        return AirSegmentIntegrationReport(
            evidence_class=evidence_class,
            telemetry_loop=telemetry_report,
            air_snapshot=air_snapshot,
            summary=summary,
            integration_fingerprint=_fingerprint(payload),
            external_network_used=telemetry_report.external_network_used,
            network_mutation=False,
        )

    @staticmethod
    def _loop_evidence(
        evidence_class: AirSegmentEvidence,
        use_udp_loopback: bool,
    ) -> NetworkLoopEvidence:
        if use_udp_loopback:
            return NetworkLoopEvidence.LOCAL_NETWORK_TEST
        if evidence_class is AirSegmentEvidence.PUBLIC_DATA:
            return NetworkLoopEvidence.PUBLIC_DATA
        return NetworkLoopEvidence.SYNTHETIC_FIXTURE

    @staticmethod
    def _summary(
        air_snapshot: AirNetworkSnapshot,
        network: AirNetwork,
        telemetry_report: NetworkTelemetryLoopReport,
        records: list[TelemetryRecord],
        reference_time_s: float,
    ) -> AirSegmentSummary:
        associations = air_snapshot.associations
        candidates = [
            candidate
            for association in associations
            for candidate in association.candidates
            if candidate.available
        ]
        margins = [candidate.link_margin_db for candidate in candidates]
        sinrs = [candidate.sinr_db for candidate in candidates]
        remaining_energy = [
            candidate.remaining_energy_wh
            for candidate in candidates
        ]
        total_demand = sum(
            association.demand_bps
            for association in associations
        )
        total_allocated = sum(
            association.allocated_capacity_bps
            for association in associations
        )
        latest_timestamp = max(
            (record.timestamp_s for record in records),
            default=reference_time_s,
        )
        loop_report = telemetry_report
        state_samples = getattr(
            loop_report,
            "state_sample_count",
            0,
        )
        return AirSegmentSummary(
            active_platform_count=sum(
                platform.active
                for platform in network.platforms
            ),
            total_platform_count=len(network.platforms),
            associated_user_count=sum(
                association.selected_platform_id is not None
                for association in associations
            ),
            unassociated_user_count=sum(
                association.selected_platform_id is None
                for association in associations
            ),
            total_demand_bps=total_demand,
            total_allocated_capacity_bps=total_allocated,
            mean_link_margin_db=(
                sum(margins) / len(margins)
                if margins
                else 0.0
            ),
            mean_sinr_db=(
                sum(sinrs) / len(sinrs)
                if sinrs
                else 0.0
            ),
            mean_remaining_energy_wh=(
                sum(remaining_energy) / len(remaining_energy)
                if remaining_energy
                else 0.0
            ),
            telemetry_sample_count=int(state_samples),
            stale_telemetry_sample_count=0,
            latest_telemetry_timestamp_s=latest_timestamp,
        )


__all__ = [
    "AirSegmentIntegrationEngine",
    "default_air_network",
    "default_air_users",
]
