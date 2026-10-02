from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.models import GeoPoint
from sag_network.ephemeris.models import (
    EphemerisSimulationConfig,
    EphemerisSourceType,
    RealSatelliteDefinition,
)
from sag_network.ephemeris.reference import SimulationEphemerisAdapter
from sag_network.ephemeris.sgp4 import SGP4EphemerisProvider
from sag_network.ephemeris.tle import parse_tle_text, tle_epoch_utc, tle_to_orbital_elements
from sag_network.network_telemetry_loop import NetworkLoopEvidence, NetworkTelemetryLoopEngine
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport
from sag_network.network_telemetry_loop.transport import SyntheticTelemetryLoopTransport
from sag_network.space.connectivity import user_satellite_candidates
from sag_network.space.real_connectivity import (
    RealEphemerisConstellation,
    user_real_satellite_candidates,
)
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.selection import SatelliteCandidate, select_best_satellite
from sag_network.telemetry.models import TelemetryRecord

from .models import (
    SpaceSegmentConfig,
    SpaceSegmentEvidence,
    SpaceSegmentIntegrationReport,
    SpaceSegmentSnapshot,
    SpaceSegmentSummary,
    SpaceUserAssociation,
)


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_space_users() -> list[MobileUser]:
    """Return deterministic ground users used as the space-segment service endpoints."""
    return [
        MobileUser(
            user_id="space-user-01",
            initial_position=GeoPoint(
                latitude_deg=17.3850,
                longitude_deg=78.4867,
                altitude_m=540.0,
            ),
        ),
        MobileUser(
            user_id="space-user-02",
            initial_position=GeoPoint(
                latitude_deg=17.4000,
                longitude_deg=78.4920,
                altitude_m=540.0,
            ),
        ),
        MobileUser(
            user_id="space-user-03",
            initial_position=GeoPoint(
                latitude_deg=17.3950,
                longitude_deg=78.4750,
                altitude_m=540.0,
            ),
        ),
    ]


def _propagation_losses() -> PropagationLosses:
    return PropagationLosses(
        atmospheric_db=1.0,
        rain_db=2.0,
        polarization_db=1.0,
        implementation_db=2.0,
    )


def _telemetry_evidence(
    evidence_class: SpaceSegmentEvidence,
    use_udp_loopback: bool,
) -> NetworkLoopEvidence:
    if use_udp_loopback:
        return NetworkLoopEvidence.LOCAL_NETWORK_TEST
    if evidence_class is SpaceSegmentEvidence.PUBLIC_DATA:
        return NetworkLoopEvidence.PUBLIC_DATA
    return NetworkLoopEvidence.SYNTHETIC_FIXTURE


def _synthetic_candidates(
    user: MobileUser,
    timestamp_s: float,
) -> list[SatelliteCandidate]:
    record_text = (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   26271.46476993  .00006013  00000+0  11848-3 0  9990\n"
        "2 25544  51.6312 148.9632 0007159 198.2260 161.8473 15.48680135587767\n"
    )
    tle = parse_tle_text(record_text, source="bundled-celestrak-fixture")
    elements = tle_to_orbital_elements(tle)
    constellation = Constellation(
        name="phase75-analytical-space",
        satellites=[
            SatelliteDefinition(
                satellite_id="iss-25544-analytical",
                orbital_elements=elements,
                minimum_elevation_deg=10.0,
            )
        ],
    )
    return user_satellite_candidates(
        constellation=constellation,
        user=user,
        timestamp_s=timestamp_s,
        carrier_frequency_hz=2.2e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30.0,
        tx_gain_dbi=8.0,
        rx_gain_dbi=0.0,
        noise_figure_db=5.0,
        propagation_losses=_propagation_losses(),
        required_sinr_db=5.0,
        interference_power_dbm=None,
    )


def _real_candidates(
    user: MobileUser,
    timestamp_s: float,
    tle_path: Path,
) -> tuple[list[SatelliteCandidate], str]:
    text = tle_path.read_text(encoding="utf-8")
    record = parse_tle_text(
        text,
        source="https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
    )
    epoch = tle_epoch_utc(record).astimezone(UTC)
    provider = SGP4EphemerisProvider.from_tle(
        record,
        satellite_id="iss-25544",
    )
    adapter = SimulationEphemerisAdapter(
        provider,
        EphemerisSimulationConfig(simulation_epoch_utc=epoch),
    )
    constellation = RealEphemerisConstellation(
        [
            (
                RealSatelliteDefinition(
                    satellite_id="iss-25544",
                    source_type=EphemerisSourceType.TLE,
                    minimum_elevation_deg=10.0,
                ),
                adapter,
            )
        ]
    )
    return (
        user_real_satellite_candidates(
            constellation=constellation,
            user=user,
            timestamp_s=timestamp_s,
            carrier_frequency_hz=2.2e9,
            bandwidth_hz=20e6,
            tx_power_dbm=30.0,
            tx_gain_dbi=8.0,
            rx_gain_dbi=0.0,
            noise_figure_db=5.0,
            propagation_losses=_propagation_losses(),
            required_sinr_db=5.0,
            simulation_epoch_timestamp_s=0.0,
        ),
        "SGP4",
    )


class SpaceSegmentIntegrationEngine:
    """Integrate canonical telemetry with the existing satellite connectivity model."""

    def __init__(self, *, tle_path: Path | None = None) -> None:
        self._telemetry = NetworkTelemetryLoopEngine()
        self._tle_path = (
            tle_path
            or Path(__file__).resolve().parents[3] / "data" / "ephemeris" / "iss-zarya.tle"
        )

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: SpaceSegmentConfig,
        evidence_class: SpaceSegmentEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> SpaceSegmentIntegrationReport:
        record_list = list(records)
        reference_time_s = config.reference_time_s
        if record_list:
            reference_time_s = max(
                reference_time_s,
                max(record.timestamp_s for record in record_list),
            )

        loop_evidence = _telemetry_evidence(
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

        users = default_space_users()
        associations: list[SpaceUserAssociation] = []
        propagation_model = "analytical-two-body"
        for user in users:
            demand = config.user_demand_bps.get(user.user_id, 8e6)
            if config.use_real_ephemeris:
                candidates, propagation_model = _real_candidates(
                    user,
                    reference_time_s,
                    self._tle_path,
                )
            else:
                candidates = _synthetic_candidates(user, reference_time_s)

            selected = select_best_satellite(candidates)
            associations.append(
                SpaceUserAssociation(
                    user_id=user.user_id,
                    demand_bps=demand,
                    selected_satellite_id=(
                        selected.satellite_id if selected is not None else None
                    ),
                    allocated_capacity_bps=(
                        min(demand, selected.shannon_capacity_bps)
                        if selected is not None
                        else 0.0
                    ),
                    candidates=candidates,
                )
            )

        snapshot = SpaceSegmentSnapshot(
            timestamp_s=reference_time_s,
            associations=associations,
        )
        summary = self._summary(
            snapshot,
            telemetry_report,
            record_list,
            reference_time_s,
            propagation_model,
            (
                "CelesTrak ISS/ZARYA TLE"
                if config.use_real_ephemeris
                else "bundled TLE analytical fixture"
            ),
            required_sinr_db=5.0,
        )
        payload = {
            "telemetry_loop": telemetry_report.model_dump(mode="json"),
            "space_snapshot": snapshot.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
        }
        return SpaceSegmentIntegrationReport(
            evidence_class=evidence_class,
            telemetry_loop=telemetry_report,
            space_snapshot=snapshot,
            summary=summary,
            integration_fingerprint=_fingerprint(payload),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            external_network_used=telemetry_report.external_network_used,
            network_mutation=False,
            hardware_measurement=False,
        )

    @staticmethod
    def _summary(
        snapshot: SpaceSegmentSnapshot,
        telemetry_report: NetworkTelemetryLoopReport,
        records: list[TelemetryRecord],
        reference_time_s: float,
        propagation_model: str,
        ephemeris_source: str,
        required_sinr_db: float,
    ) -> SpaceSegmentSummary:
        candidates = [
            candidate
            for association in snapshot.associations
            for candidate in association.candidates
            if candidate.available
        ]
        margins = [candidate.link_margin_db for candidate in candidates]
        elevations = [candidate.elevation_deg for candidate in candidates]
        delays = [candidate.propagation_delay_ms for candidate in candidates]
        dopplers = [candidate.doppler_shift_hz for candidate in candidates]
        demands = [association.demand_bps for association in snapshot.associations]
        allocated = [
            association.allocated_capacity_bps
            for association in snapshot.associations
        ]
        latest = max(
            (record.timestamp_s for record in records),
            default=reference_time_s,
        )
        state_sample_count = telemetry_report.state_sample_count
        return SpaceSegmentSummary(
            active_satellite_count=1,
            total_satellite_count=1,
            associated_user_count=sum(
                association.selected_satellite_id is not None
                for association in snapshot.associations
            ),
            unassociated_user_count=sum(
                association.selected_satellite_id is None
                for association in snapshot.associations
            ),
            total_demand_bps=sum(demands),
            total_allocated_capacity_bps=sum(allocated),
            mean_link_margin_db=(sum(margins) / len(margins)) if margins else 0.0,
            mean_sinr_db=(
                sum(
                    candidate.link_margin_db + required_sinr_db
                    for candidate in candidates
                )
                / len(candidates)
                if candidates
                else 0.0
            ),
            mean_elevation_deg=(sum(elevations) / len(elevations)) if elevations else 0.0,
            mean_propagation_delay_ms=(sum(delays) / len(delays)) if delays else 0.0,
            mean_doppler_shift_hz=(sum(dopplers) / len(dopplers)) if dopplers else 0.0,
            telemetry_sample_count=int(state_sample_count),
            stale_telemetry_sample_count=0,
            latest_telemetry_timestamp_s=latest,
            propagation_model=propagation_model,
            ephemeris_source=ephemeris_source,
        )
