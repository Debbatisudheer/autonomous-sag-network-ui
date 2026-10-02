from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from sag_network.domain.ground import GroundCell, GroundNetwork, GroundNetworkSnapshot
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.models import GeoPoint
from sag_network.ground.association import evaluate_ground_network
from sag_network.ground_segment.models import (
    GroundSegmentConfig,
    GroundSegmentEvidence,
    GroundSegmentIntegrationReport,
    GroundSegmentSummary,
)
from sag_network.network_telemetry_loop import NetworkLoopEvidence, NetworkTelemetryLoopEngine
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


def default_ground_network() -> GroundNetwork:
    """Return a deterministic pair of Hyderabad-region ground cells for integration tests."""
    propagation = PropagationLosses(
        atmospheric_db=1.0,
        rain_db=2.0,
        polarization_db=1.0,
        implementation_db=2.0,
    )
    return GroundNetwork(
        name="phase73-ground-segment",
        cells=[
            GroundCell(
                cell_id="ground-cell-01",
                position=GeoPoint(
                    latitude_deg=17.3850,
                    longitude_deg=78.4867,
                    altitude_m=540.0,
                ),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=43.0,
                tx_gain_dbi=14.0,
                rx_gain_dbi=0.0,
                noise_figure_db=5.0,
                required_sinr_db=8.0,
                maximum_service_distance_m=6_000.0,
                propagation_losses=propagation,
            ),
            GroundCell(
                cell_id="ground-cell-02",
                position=GeoPoint(
                    latitude_deg=17.3950,
                    longitude_deg=78.4867,
                    altitude_m=540.0,
                ),
                carrier_frequency_hz=3.5e9,
                bandwidth_hz=20e6,
                tx_power_dbm=43.0,
                tx_gain_dbi=14.0,
                rx_gain_dbi=0.0,
                noise_figure_db=5.0,
                required_sinr_db=8.0,
                maximum_service_distance_m=6_000.0,
                propagation_losses=propagation,
            ),
        ],
    )


def default_ground_users() -> list[MobileUser]:
    return [
        MobileUser(
            user_id="ground-user-01",
            initial_position=GeoPoint(
                latitude_deg=17.3850,
                longitude_deg=78.4867,
                altitude_m=540.0,
            ),
        ),
        MobileUser(
            user_id="ground-user-02",
            initial_position=GeoPoint(
                latitude_deg=17.3950,
                longitude_deg=78.4867,
                altitude_m=540.0,
            ),
        ),
    ]


class GroundSegmentIntegrationEngine:
    """Integrate network telemetry state with the existing terrestrial ground-network model."""

    def __init__(self) -> None:
        self._telemetry = NetworkTelemetryLoopEngine()

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: GroundSegmentConfig,
        evidence_class: GroundSegmentEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> GroundSegmentIntegrationReport:
        record_list = list(records)
        reference_time_s = config.reference_time_s
        if record_list:
            reference_time_s = max(reference_time_s, max(r.timestamp_s for r in record_list))

        loop_evidence = self._loop_evidence(evidence_class, config.use_udp_loopback)
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
            from sag_network.network_telemetry_loop.transport import SyntheticTelemetryLoopTransport

            telemetry_report = self._telemetry.run(
                record_list,
                reference_time_s=reference_time_s,
                transport=SyntheticTelemetryLoopTransport(),
                evidence_class=loop_evidence,
                source_sha256=source_sha256,
                provenance_verified=provenance_verified,
                timeout_s=config.timeout_s,
            )

        network = default_ground_network()
        users = default_ground_users()
        demands = {
            user.user_id: config.user_demand_bps.get(user.user_id, 5e6)
            for user in users
        }
        ground_snapshot = evaluate_ground_network(
            network=network,
            users=users,
            demands_bps=demands,
            timestamp_s=reference_time_s,
        )
        summary = self._summary(
            ground_snapshot,
            network,
            telemetry_report,
            record_list,
            reference_time_s,
        )
        payload = {
            "telemetry_loop": telemetry_report.model_dump(mode="json"),
            "ground_snapshot": ground_snapshot.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
        }
        return GroundSegmentIntegrationReport(
            evidence_class=evidence_class,
            telemetry_loop=telemetry_report,
            ground_snapshot=ground_snapshot,
            summary=summary,
            integration_fingerprint=_fingerprint(payload),
            external_network_used=telemetry_report.external_network_used,
            network_mutation=False,
        )

    @staticmethod
    def _loop_evidence(
        evidence_class: GroundSegmentEvidence,
        use_udp_loopback: bool,
    ) -> NetworkLoopEvidence:
        if use_udp_loopback:
            return NetworkLoopEvidence.LOCAL_NETWORK_TEST
        if evidence_class is GroundSegmentEvidence.PUBLIC_DATA:
            return NetworkLoopEvidence.PUBLIC_DATA
        return NetworkLoopEvidence.SYNTHETIC_FIXTURE

    @staticmethod
    def _summary(
        ground_snapshot: GroundNetworkSnapshot,
        network: GroundNetwork,
        telemetry_report: object,
        records: list[TelemetryRecord],
        reference_time_s: float,
    ) -> GroundSegmentSummary:
        associations = ground_snapshot.associations
        candidates = [
            candidate
            for association in associations
            for candidate in association.candidates
            if candidate.available
        ]
        margins = [candidate.link_margin_db for candidate in candidates]
        sinrs = [candidate.sinr_db for candidate in candidates]
        total_demand = sum(association.demand_bps for association in associations)
        total_allocated = sum(
            association.allocated_capacity_bps for association in associations
        )
        latest_timestamp = max(
            (record.timestamp_s for record in records),
            default=reference_time_s,
        )
        loop_report = telemetry_report
        state_samples = getattr(loop_report, "state_sample_count", 0)
        return GroundSegmentSummary(
            active_cell_count=sum(cell.active for cell in network.cells),
            total_cell_count=len(network.cells),
            associated_user_count=sum(
                association.selected_cell_id is not None
                for association in associations
            ),
            unassociated_user_count=sum(
                association.selected_cell_id is None
                for association in associations
            ),
            total_demand_bps=total_demand,
            total_allocated_capacity_bps=total_allocated,
            mean_link_margin_db=sum(margins) / len(margins) if margins else 0.0,
            mean_sinr_db=sum(sinrs) / len(sinrs) if sinrs else 0.0,
            telemetry_sample_count=int(state_samples),
            stale_telemetry_sample_count=0,
            latest_telemetry_timestamp_s=latest_timestamp,
        )


__all__ = ["GroundSegmentIntegrationEngine", "default_ground_network", "default_ground_users"]
