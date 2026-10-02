from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC
from pathlib import Path

from sag_network.air.link import air_user_link_state
from sag_network.domain.air import AirNetwork
from sag_network.domain.constellation import Constellation, SatelliteDefinition
from sag_network.domain.ground import GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser, MobilityProfile
from sag_network.domain.models import GeoPoint
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
    UnifiedUserAssociation,
)
from sag_network.ephemeris.models import (
    EphemerisSimulationConfig,
    EphemerisSourceType,
    RealSatelliteDefinition,
)
from sag_network.ephemeris.reference import SimulationEphemerisAdapter
from sag_network.ephemeris.sgp4 import SGP4EphemerisProvider
from sag_network.ephemeris.tle import parse_tle_text, tle_epoch_utc, tle_to_orbital_elements
from sag_network.ground.link import ground_user_link_state
from sag_network.network_telemetry_loop import (
    NetworkLoopEvidence,
    NetworkTelemetryLoopEngine,
)
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport
from sag_network.network_telemetry_loop.transport import SyntheticTelemetryLoopTransport
from sag_network.space.link import satellite_link_state
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.real_connectivity import (
    RealEphemerisConstellation,
    user_real_satellite_candidates,
)
from sag_network.space.selection import SatelliteCandidate
from sag_network.telemetry.models import TelemetryRecord

from .models import (
    CrossDomainSAGConfig,
    CrossDomainSAGEvidence,
    CrossDomainSAGIntegrationReport,
    CrossDomainSAGSummary,
)


_TLE_SOURCE = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_cross_domain_users() -> list[MobileUser]:
    """Return one shared three-user population used by all three network domains."""
    return [
        MobileUser(
            user_id="sag-user-01",
            initial_position=GeoPoint(
                latitude_deg=17.3850,
                longitude_deg=78.4867,
                altitude_m=540.0,
            ),
            mobility=MobilityProfile(north_velocity_mps=5.0, east_velocity_mps=2.0),
        ),
        MobileUser(
            user_id="sag-user-02",
            initial_position=GeoPoint(
                latitude_deg=17.4000,
                longitude_deg=78.4920,
                altitude_m=540.0,
            ),
            mobility=MobilityProfile(north_velocity_mps=-2.0, east_velocity_mps=4.0),
        ),
        MobileUser(
            user_id="sag-user-03",
            initial_position=GeoPoint(
                latitude_deg=17.3950,
                longitude_deg=78.4750,
                altitude_m=540.0,
            ),
            mobility=MobilityProfile(north_velocity_mps=1.0, east_velocity_mps=-3.0),
        ),
    ]


def default_ground_network() -> GroundNetwork:
    from sag_network.ground_segment.engine import (
        default_ground_network as phase73_ground_network,
    )

    source = phase73_ground_network()
    return source.model_copy(deep=True, update={"name": "phase76-ground-segment"})


def default_air_network() -> AirNetwork:
    from sag_network.air_segment.engine import default_air_network as phase74_air_network

    source = phase74_air_network()
    return source.model_copy(deep=True, update={"name": "phase76-air-segment"})


def _ground_candidates(
    network: GroundNetwork,
    user: MobileUser,
    timestamp_s: float,
) -> list[UnifiedCandidate]:
    candidates: list[UnifiedCandidate] = []
    for cell in network.cells:
        link = ground_user_link_state(cell=cell, user=user, timestamp_s=timestamp_s)
        candidates.append(
            UnifiedCandidate(
                resource_id=link.cell_id,
                domain=NetworkDomain.GROUND,
                resource_type="ground_cell",
                available=link.available,
                distance_m=link.distance_m,
                rx_power_dbm=link.rx_power_dbm,
                noise_power_dbm=link.noise_power_dbm,
                sinr_db=link.sinr_db,
                link_margin_db=link.link_margin_db,
                shannon_capacity_bps=link.shannon_capacity_bps,
                estimated_capacity_bps=link.estimated_capacity_bps,
                propagation_delay_ms=link.distance_m / 299_792_458.0 * 1_000.0,
            )
        )
    return candidates


def _air_candidates(
    network: AirNetwork,
    user: MobileUser,
    timestamp_s: float,
) -> list[UnifiedCandidate]:
    candidates: list[UnifiedCandidate] = []
    for platform in network.platforms:
        link = air_user_link_state(platform=platform, user=user, timestamp_s=timestamp_s)
        candidates.append(
            UnifiedCandidate(
                resource_id=link.platform_id,
                domain=NetworkDomain.AIR,
                resource_type=link.platform_type.value,
                available=link.available,
                distance_m=link.distance_m,
                rx_power_dbm=link.rx_power_dbm,
                noise_power_dbm=link.noise_power_dbm,
                sinr_db=link.sinr_db,
                link_margin_db=link.link_margin_db,
                shannon_capacity_bps=link.shannon_capacity_bps,
                estimated_capacity_bps=link.estimated_capacity_bps,
                propagation_delay_ms=link.distance_m / 299_792_458.0 * 1_000.0,
                remaining_energy_wh=link.remaining_energy_wh,
                time_to_reserve_s=link.time_to_reserve_s,
            )
        )
    return candidates


def _synthetic_space_candidates(
    user: MobileUser,
    timestamp_s: float,
    tle_path: Path,
) -> list[UnifiedCandidate]:
    tle = parse_tle_text(
        tle_path.read_text(encoding="utf-8"),
        source="bundled-celestrak-fixture",
    )
    elements = tle_to_orbital_elements(tle)
    constellation = Constellation(
        name="phase76-analytical-space",
        satellites=[
            SatelliteDefinition(
                satellite_id="iss-25544-analytical",
                orbital_elements=elements,
                minimum_elevation_deg=10.0,
            )
        ],
    )
    position = user.position_at(timestamp_s)
    candidates: list[UnifiedCandidate] = []
    for satellite in constellation.satellites:
        state = propagate_satellite_state(
            satellite.orbital_elements, timestamp_s
        )
        link = satellite_link_state(
            timestamp_s=timestamp_s,
            ground_station_id=user.user_id,
            ground_position=position,
            satellite_position_ecef=state.position_ecef,
            satellite_velocity_ecef=state.velocity_ecef,
            carrier_frequency_hz=2.2e9,
            bandwidth_hz=20e6,
            tx_power_dbm=30.0,
            tx_gain_dbi=8.0,
            rx_gain_dbi=0.0,
            noise_figure_db=5.0,
            propagation_losses=PropagationLosses(
                atmospheric_db=1.0,
                rain_db=2.0,
                polarization_db=1.0,
                implementation_db=2.0,
            ),
            required_sinr_db=5.0,
        )
        candidates.append(
            UnifiedCandidate(
                resource_id=satellite.satellite_id,
                domain=NetworkDomain.SPACE,
                resource_type="leo_satellite",
                available=bool(link["available"]),
                distance_m=float(link["slant_range_m"]),
                rx_power_dbm=float(link["rx_power_dbm"]),
                noise_power_dbm=float(link["noise_power_dbm"]),
                sinr_db=float(link["sinr_db"]),
                link_margin_db=float(link["link_margin_db"]),
                shannon_capacity_bps=float(link["shannon_capacity_bps"]),
                estimated_capacity_bps=float(link["shannon_capacity_bps"]),
                propagation_delay_ms=float(link["propagation_delay_ms"]),
                doppler_shift_hz=float(link["doppler_shift_hz"]),
            )
        )
    return candidates


def _real_space_candidates(
    user: MobileUser,
    timestamp_s: float,
    tle_path: Path,
) -> list[UnifiedCandidate]:
    record = parse_tle_text(tle_path.read_text(encoding="utf-8"), source=_TLE_SOURCE)
    epoch = tle_epoch_utc(record).astimezone(UTC)
    provider = SGP4EphemerisProvider.from_tle(record, satellite_id="iss-25544")
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
    candidates: list[SatelliteCandidate] = user_real_satellite_candidates(
        constellation=constellation,
        user=user,
        timestamp_s=timestamp_s,
        carrier_frequency_hz=2.2e9,
        bandwidth_hz=20e6,
        tx_power_dbm=30.0,
        tx_gain_dbi=8.0,
        rx_gain_dbi=0.0,
        noise_figure_db=5.0,
        propagation_losses=PropagationLosses(
            atmospheric_db=1.0,
            rain_db=2.0,
            polarization_db=1.0,
            implementation_db=2.0,
        ),
        required_sinr_db=5.0,
        simulation_epoch_timestamp_s=0.0,
    )
    return [
        UnifiedCandidate(
            resource_id=candidate.satellite_id,
            domain=NetworkDomain.SPACE,
            resource_type="leo_satellite",
            available=candidate.available,
            distance_m=max(candidate.propagation_delay_ms / 1_000.0 * 299_792_458.0, 1.0),
            rx_power_dbm=0.0,
            noise_power_dbm=0.0,
            sinr_db=candidate.link_margin_db + 5.0,
            link_margin_db=candidate.link_margin_db,
            shannon_capacity_bps=candidate.shannon_capacity_bps,
            estimated_capacity_bps=candidate.shannon_capacity_bps,
            propagation_delay_ms=candidate.propagation_delay_ms,
            doppler_shift_hz=candidate.doppler_shift_hz,
            predicted_loss_time_s=candidate.predicted_loss_time_s,
        )
        for candidate in candidates
    ]


def _choose_candidate(
    candidates: list[UnifiedCandidate],
    assigned_users: dict[str, int],
) -> UnifiedCandidate | None:
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def sort_key(
        candidate: UnifiedCandidate,
    ) -> tuple[float, float, float, float, float, float, str]:
        user_count = assigned_users.get(candidate.resource_id, 0)
        shared_rate = candidate.estimated_capacity_bps / (user_count + 1)
        reserve_horizon = (
            float("inf")
            if candidate.time_to_reserve_s is None
            else candidate.time_to_reserve_s
        )
        domain_order = {
            NetworkDomain.GROUND: 2.0,
            NetworkDomain.AIR: 1.0,
            NetworkDomain.SPACE: 0.0,
        }
        return (
            shared_rate,
            candidate.link_margin_db,
            reserve_horizon,
            candidate.sinr_db,
            -candidate.propagation_delay_ms,
            domain_order[candidate.domain],
            candidate.resource_id,
        )

    return max(available, key=sort_key)


def _telemetry_evidence(
    evidence_class: CrossDomainSAGEvidence,
    use_udp_loopback: bool,
) -> NetworkLoopEvidence:
    if use_udp_loopback:
        return NetworkLoopEvidence.LOCAL_NETWORK_TEST
    if evidence_class is CrossDomainSAGEvidence.PUBLIC_DATA:
        return NetworkLoopEvidence.PUBLIC_DATA
    return NetworkLoopEvidence.SYNTHETIC_FIXTURE


class CrossDomainSAGIntegrationEngine:
    """Compose Ground, Air, and Space connectivity into one common SAG state."""

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
        config: CrossDomainSAGConfig,
        evidence_class: CrossDomainSAGEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> CrossDomainSAGIntegrationReport:
        record_list = list(records)
        reference_time_s = config.reference_time_s
        if record_list:
            reference_time_s = max(
                reference_time_s,
                max(record.timestamp_s for record in record_list),
            )

        loop_evidence = _telemetry_evidence(evidence_class, config.use_udp_loopback)
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

        ground = default_ground_network()
        air = default_air_network()
        users = default_cross_domain_users()
        demands = {
            user.user_id: config.user_demand_bps.get(user.user_id, 10e6)
            for user in users
        }

        assigned_users: dict[str, int] = {}
        associations: list[UnifiedUserAssociation] = []
        propagation_model = "SGP4" if config.use_real_ephemeris else "analytical-two-body"
        ephemeris_source = (
            "CelesTrak ISS/ZARYA TLE"
            if config.use_real_ephemeris
            else "bundled TLE analytical fixture"
        )

        for user in sorted(users, key=lambda item: item.user_id):
            candidates = [
                *_ground_candidates(ground, user, reference_time_s),
                *_air_candidates(air, user, reference_time_s),
            ]
            if config.use_real_ephemeris:
                candidates.extend(
                    _real_space_candidates(user, reference_time_s, self._tle_path)
                )
            else:
                candidates.extend(_synthetic_space_candidates(user, reference_time_s, self._tle_path))

            selected = _choose_candidate(candidates, assigned_users)
            if selected is None:
                selected_id = None
                selected_domain = None
                allocated = 0.0
            else:
                selected_id = selected.resource_id
                selected_domain = selected.domain
                count = assigned_users.get(selected.resource_id, 0) + 1
                allocated = min(demands[user.user_id], selected.estimated_capacity_bps / count)
                assigned_users[selected.resource_id] = count

            associations.append(
                UnifiedUserAssociation(
                    user_id=user.user_id,
                    selected_resource_id=selected_id,
                    selected_domain=selected_domain,
                    demand_bps=demands[user.user_id],
                    allocated_capacity_bps=allocated,
                    candidates=candidates,
                )
            )

        snapshot = UnifiedNetworkSnapshot(
            timestamp_s=reference_time_s,
            associations=associations,
        )
        summary = self._summary(snapshot, telemetry_report, record_list, reference_time_s)
        payload = {
            "telemetry_loop": telemetry_report.model_dump(mode="json"),
            "unified_snapshot": snapshot.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
            "propagation_model": propagation_model,
            "ephemeris_source": ephemeris_source,
        }
        return CrossDomainSAGIntegrationReport(
            evidence_class=evidence_class,
            telemetry_loop=telemetry_report,
            unified_snapshot=snapshot,
            summary=summary,
            integration_fingerprint=_fingerprint(payload),
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
            propagation_model=propagation_model,
            ephemeris_source=ephemeris_source,
            external_network_used=telemetry_report.external_network_used,
            network_mutation=False,
            hardware_measurement=False,
        )

    @staticmethod
    def _summary(
        snapshot: UnifiedNetworkSnapshot,
        telemetry_report: NetworkTelemetryLoopReport,
        records: list[TelemetryRecord],
        reference_time_s: float,
    ) -> CrossDomainSAGSummary:
        associations = snapshot.associations
        candidates = [
            candidate
            for association in associations
            for candidate in association.candidates
        ]
        available = [candidate for candidate in candidates if candidate.available]
        selected = [
            candidate
            for association in associations
            if association.selected_resource_id is not None
            for candidate in association.candidates
            if candidate.resource_id == association.selected_resource_id
        ]
        total_demand = sum(association.demand_bps for association in associations)
        total_allocated = sum(
            association.allocated_capacity_bps for association in associations
        )
        selected_domains = [
            association.selected_domain
            for association in associations
            if association.selected_domain is not None
        ]
        air_energy = [
            candidate.remaining_energy_wh
            for candidate in available
            if candidate.remaining_energy_wh is not None
        ]
        latest = max((record.timestamp_s for record in records), default=reference_time_s)

        return CrossDomainSAGSummary(
            total_user_count=len(associations),
            associated_user_count=sum(
                association.selected_resource_id is not None
                for association in associations
            ),
            unassociated_user_count=sum(
                association.selected_resource_id is None
                for association in associations
            ),
            total_demand_bps=total_demand,
            total_allocated_capacity_bps=total_allocated,
            unmet_demand_bps=max(total_demand - total_allocated, 0.0),
            total_candidate_count=len(candidates),
            available_candidate_count=len(available),
            ground_candidate_count=sum(
                candidate.domain is NetworkDomain.GROUND for candidate in candidates
            ),
            air_candidate_count=sum(
                candidate.domain is NetworkDomain.AIR for candidate in candidates
            ),
            space_candidate_count=sum(
                candidate.domain is NetworkDomain.SPACE for candidate in candidates
            ),
            selected_ground_count=sum(
                domain is NetworkDomain.GROUND for domain in selected_domains
            ),
            selected_air_count=sum(
                domain is NetworkDomain.AIR for domain in selected_domains
            ),
            selected_space_count=sum(
                domain is NetworkDomain.SPACE for domain in selected_domains
            ),
            coverage_ratio=(
                total_allocated / total_demand
                if total_demand
                else 1.0
            ),
            mean_link_margin_db=(
                sum(candidate.link_margin_db for candidate in selected) / len(selected)
                if selected
                else 0.0
            ),
            mean_sinr_db=(
                sum(candidate.sinr_db for candidate in selected) / len(selected)
                if selected
                else 0.0
            ),
            mean_propagation_delay_ms=(
                sum(candidate.propagation_delay_ms for candidate in selected) / len(selected)
                if selected
                else 0.0
            ),
            mean_doppler_shift_hz=(
                sum(
                    candidate.doppler_shift_hz or 0.0
                    for candidate in selected
                    if candidate.domain is NetworkDomain.SPACE
                )
                / max(
                    sum(
                        candidate.domain is NetworkDomain.SPACE
                        for candidate in selected
                    ),
                    1,
                )
            ),
            mean_air_remaining_energy_wh=(
                sum(air_energy) / len(air_energy)
                if air_energy
                else 0.0
            ),
            telemetry_sample_count=telemetry_report.state_sample_count,
            stale_telemetry_sample_count=0,
            latest_telemetry_timestamp_s=latest,
        )


__all__ = [
    "CrossDomainSAGIntegrationEngine",
    "default_cross_domain_users",
    "default_ground_network",
    "default_air_network",
]
