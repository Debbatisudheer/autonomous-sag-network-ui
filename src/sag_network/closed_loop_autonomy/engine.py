from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable

from sag_network.cross_domain_sag import (
    CrossDomainSAGConfig,
    CrossDomainSAGEvidence,
    CrossDomainSAGIntegrationEngine,
)
from sag_network.domain.unified import (
    NetworkDomain,
    UnifiedCandidate,
    UnifiedNetworkSnapshot,
)
from sag_network.domain.unified_handover import (
    UnifiedHandoverEvent,
    UnifiedHandoverEventType,
    UnifiedHandoverPolicy,
)
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport
from sag_network.telemetry.models import TelemetryRecord
from sag_network.unified.handover import UnifiedHandoverController

from .models import (
    AutonomyAction,
    AutonomyCycleResult,
    ClosedLoopAutonomyConfig,
    ClosedLoopAutonomyReport,
    ClosedLoopAutonomySummary,
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


def _telemetry_health(report: NetworkTelemetryLoopReport) -> float:
    accepted = float(report.accepted_record_count)
    received = float(report.received_record_count)
    if received <= 0:
        return 0.0
    return min(1.0, max(0.0, accepted / received))


def _best_available(candidates: list[UnifiedCandidate]) -> UnifiedCandidate | None:
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def key(candidate: UnifiedCandidate) -> tuple[float, float, float, float, float, str]:
        return (
            candidate.link_margin_db,
            candidate.estimated_capacity_bps,
            candidate.sinr_db,
            -candidate.propagation_delay_ms,
            candidate.remaining_energy_wh or 0.0,
            candidate.resource_id,
        )

    return max(available, key=key)


def _candidate_by_id(
    candidates: list[UnifiedCandidate], resource_id: str | None
) -> UnifiedCandidate | None:
    if resource_id is None:
        return None
    return next(
        (candidate for candidate in candidates if candidate.resource_id == resource_id),
        None,
    )


def _action_from_event(event_type: UnifiedHandoverEventType) -> AutonomyAction:
    return {
        UnifiedHandoverEventType.ATTACH: AutonomyAction.ATTACH,
        UnifiedHandoverEventType.RETAIN: AutonomyAction.RETAIN,
        UnifiedHandoverEventType.HANDOVER: AutonomyAction.HANDOVER,
        UnifiedHandoverEventType.NO_COVERAGE: AutonomyAction.NO_COVERAGE,
    }[event_type]


class ClosedLoopAutonomyEngine:
    """Run an observe-decide-act-verify loop over the Phase 76 SAG state model.

    The loop is software-only: the action actuator updates controller state but
    never mutates external network infrastructure or RF hardware.
    """

    def __init__(self, *, cross_domain: CrossDomainSAGIntegrationEngine | None = None) -> None:
        self._cross_domain = cross_domain or CrossDomainSAGIntegrationEngine()

    def _snapshot(
        self,
        *,
        timestamp_s: float,
        config: ClosedLoopAutonomyConfig,
        evidence_class: CrossDomainSAGEvidence,
    ) -> tuple[UnifiedNetworkSnapshot, str, str]:
        result = self._cross_domain.run(
            [],
            config=CrossDomainSAGConfig(
                reference_time_s=timestamp_s,
                user_demand_bps=config.user_demand_bps,
                use_udp_loopback=False,
                timeout_s=config.timeout_s,
                use_real_ephemeris=config.use_real_ephemeris,
            ),
            evidence_class=evidence_class,
        )
        return result.unified_snapshot, result.propagation_model, result.ephemeris_source

    @staticmethod
    def _verify(
        *,
        selected: UnifiedCandidate | None,
        demand_bps: float,
        event: UnifiedHandoverEvent,
        telemetry_gate_open: bool,
    ) -> tuple[bool, str]:
        if not telemetry_gate_open:
            if event.event_type in {
                UnifiedHandoverEventType.ATTACH,
                UnifiedHandoverEventType.HANDOVER,
            }:
                return False, "telemetry gate blocked state-changing action"
            return True, "telemetry gate closed; no state-changing action was issued"
        if event.event_type is UnifiedHandoverEventType.NO_COVERAGE:
            return selected is None, "no-coverage state is consistent"
        if selected is None or not selected.available:
            return False, "selected serving resource is unavailable"
        if selected.estimated_capacity_bps + 1e-9 < demand_bps:
            return False, "selected serving resource cannot satisfy demand"
        return True, "serving resource is available and satisfies demand"

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: ClosedLoopAutonomyConfig,
        evidence_class: CrossDomainSAGEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> ClosedLoopAutonomyReport:
        record_list = list(records)
        final_time = config.timestamps_s[-1]

        telemetry_result = self._cross_domain.run(
            record_list,
            config=CrossDomainSAGConfig(
                reference_time_s=final_time,
                user_demand_bps=config.user_demand_bps,
                use_udp_loopback=config.use_udp_loopback,
                timeout_s=config.timeout_s,
                use_real_ephemeris=config.use_real_ephemeris,
            ),
            evidence_class=evidence_class,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )
        telemetry_report = telemetry_result.telemetry_loop
        effective_source_sha = telemetry_result.source_sha256
        effective_provenance = telemetry_result.provenance_verified
        telemetry_health = _telemetry_health(telemetry_report)
        telemetry_gate_open = telemetry_health >= config.minimum_telemetry_health

        controllers: dict[str, UnifiedHandoverController] = {}
        cycles: list[AutonomyCycleResult] = []
        propagation_model = telemetry_result.propagation_model
        ephemeris_source = telemetry_result.ephemeris_source

        for timestamp_s in config.timestamps_s:
            snapshot, propagation_model, ephemeris_source = self._snapshot(
                timestamp_s=timestamp_s,
                config=config,
                evidence_class=evidence_class,
            )
            for association in snapshot.associations:
                controller = controllers.setdefault(
                    association.user_id,
                    UnifiedHandoverController(
                        policy=UnifiedHandoverPolicy(
                            hysteresis_db=config.handover_hysteresis_db,
                            time_to_trigger_s=config.handover_time_to_trigger_s,
                        )
                    ),
                )
                if not telemetry_gate_open:
                    event = UnifiedHandoverEvent(
                        timestamp_s=timestamp_s,
                        user_id=association.user_id,
                        event_type=(
                            UnifiedHandoverEventType.NO_COVERAGE
                            if controller.serving_resource_id is None
                            else UnifiedHandoverEventType.RETAIN
                        ),
                        previous_resource_id=controller.serving_resource_id,
                        previous_domain=None,
                        new_resource_id=controller.serving_resource_id,
                        new_domain=None,
                        reason="telemetry_health_below_autonomous_action_threshold",
                    )
                else:
                    event = controller.update(
                        user_id=association.user_id,
                        timestamp_s=timestamp_s,
                        candidates=association.candidates,
                    )

                selected = _candidate_by_id(association.candidates, controller.serving_resource_id)
                best = _best_available(association.candidates)
                action = _action_from_event(event.event_type)
                verification_passed, verification_reason = self._verify(
                    selected=selected,
                    demand_bps=association.demand_bps,
                    event=event,
                    telemetry_gate_open=telemetry_gate_open,
                )
                if telemetry_gate_open:
                    reason = event.reason
                else:
                    reason = "autonomous state-changing action suppressed by telemetry health gate"
                cycles.append(
                    AutonomyCycleResult(
                        timestamp_s=timestamp_s,
                        user_id=association.user_id,
                        previous_resource_id=event.previous_resource_id,
                        previous_domain=event.previous_domain,
                        selected_resource_id=event.new_resource_id,
                        selected_domain=event.new_domain,
                        best_available_resource_id=None if best is None else best.resource_id,
                        best_available_domain=None if best is None else best.domain,
                        best_link_margin_db=None if best is None else best.link_margin_db,
                        selected_capacity_bps=(
                            0.0 if selected is None else selected.estimated_capacity_bps
                        ),
                        demand_bps=association.demand_bps,
                        demand_satisfied=selected is not None
                        and selected.available
                        and selected.estimated_capacity_bps >= association.demand_bps,
                        telemetry_health=telemetry_health,
                        telemetry_gate_open=telemetry_gate_open,
                        decision_action=action if telemetry_gate_open else AutonomyAction.BLOCKED,
                        handover_event_type=event.event_type,
                        decision_reason=reason,
                        verification_passed=verification_passed,
                        verification_reason=verification_reason,
                    )
                )

        counts = Counter(cycle.decision_action for cycle in cycles)
        verification_pass = sum(cycle.verification_passed for cycle in cycles)
        satisfied = sum(cycle.demand_satisfied for cycle in cycles)
        users = {cycle.user_id for cycle in cycles}
        final_cycles = [cycle for cycle in cycles if cycle.timestamp_s == final_time]
        final_serving = sum(cycle.selected_resource_id is not None for cycle in final_cycles)
        summary = ClosedLoopAutonomySummary(
            cycle_count=len(cycles),
            user_count=len(users),
            associated_cycle_count=satisfied,
            handover_count=counts[AutonomyAction.HANDOVER],
            attach_count=counts[AutonomyAction.ATTACH],
            retain_count=counts[AutonomyAction.RETAIN],
            no_coverage_count=counts[AutonomyAction.NO_COVERAGE],
            blocked_count=counts[AutonomyAction.BLOCKED],
            verification_pass_count=verification_pass,
            verification_fail_count=len(cycles) - verification_pass,
            telemetry_health_mean=(
                sum(cycle.telemetry_health for cycle in cycles) / len(cycles)
                if cycles
                else telemetry_health
            ),
            demand_satisfaction_ratio=satisfied / len(cycles) if cycles else 0.0,
            autonomous_action_rate=(
                sum(
                    cycle.decision_action
                    in {AutonomyAction.ATTACH, AutonomyAction.HANDOVER, AutonomyAction.RETAIN}
                    for cycle in cycles
                )
                / len(cycles)
                if cycles
                else 0.0
            ),
            final_serving_users=final_serving,
        )
        payload = {
            "telemetry": telemetry_report.model_dump(mode="json"),
            "cycles": [cycle.model_dump(mode="json") for cycle in cycles],
            "summary": summary.model_dump(mode="json"),
            "propagation_model": propagation_model,
            "ephemeris_source": ephemeris_source,
        }
        return ClosedLoopAutonomyReport(
            evidence_class=evidence_class,
            telemetry_loop=telemetry_report,
            cycles=cycles,
            summary=summary,
            integration_fingerprint=_fingerprint(payload),
            source_sha256=effective_source_sha,
            provenance_verified=effective_provenance,
            propagation_model=propagation_model,
            ephemeris_source=ephemeris_source,
            external_network_used=telemetry_report.external_network_used,
            network_mutation=False,
            hardware_measurement=False,
        )


__all__ = ["ClosedLoopAutonomyEngine"]
