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
from sag_network.domain.unified import NetworkDomain, UnifiedCandidate, UnifiedNetworkSnapshot
from sag_network.domain.unified_handover import (
    UnifiedHandoverEventType,
    UnifiedHandoverPolicy,
)
from sag_network.network_telemetry_loop.models import NetworkTelemetryLoopReport
from sag_network.telemetry.models import TelemetryRecord
from sag_network.unified.handover import UnifiedHandoverController

from .models import (
    ResilienceCampaignConfig,
    ResilienceCampaignReport,
    ResilienceCampaignSummary,
    ResilienceCycleResult,
    ResilienceFailureMode,
    ResilienceScenario,
    ResilienceScenarioResult,
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
    received = float(report.received_record_count)
    if received <= 0:
        return 0.0
    return min(1.0, max(0.0, report.accepted_record_count / received))


def _candidate_available(candidate: UnifiedCandidate) -> bool:
    return candidate.available and candidate.estimated_capacity_bps > 0.0


def _best_available(candidates: list[UnifiedCandidate]) -> UnifiedCandidate | None:
    available = [candidate for candidate in candidates if candidate.available]
    if not available:
        return None

    def key(candidate: UnifiedCandidate) -> tuple[float, float, float, float, str]:
        return (
            candidate.link_margin_db,
            candidate.estimated_capacity_bps,
            candidate.sinr_db,
            -candidate.propagation_delay_ms,
            candidate.resource_id,
        )

    return max(available, key=key)


def _candidate_by_id(
    candidates: list[UnifiedCandidate],
    resource_id: str | None,
) -> UnifiedCandidate | None:
    if resource_id is None:
        return None
    return next(
        (candidate for candidate in candidates if candidate.resource_id == resource_id),
        None,
    )


def _apply_fault(
    candidates: list[UnifiedCandidate],
    *,
    scenario: ResilienceScenario,
    failure_active: bool,
) -> list[UnifiedCandidate]:
    if not failure_active:
        return [candidate.model_copy(deep=True) for candidate in candidates]

    affected_ids = set(scenario.affected_resource_ids)
    affected_domains = set(scenario.affected_domains)
    degraded: list[UnifiedCandidate] = []
    for candidate in candidates:
        update: dict[str, object] = {}
        affected = False
        if scenario.failure_mode in {
            ResilienceFailureMode.RESOURCE_OUTAGE,
            ResilienceFailureMode.CASCADING_OUTAGE,
        } and candidate.resource_id in affected_ids:
            affected = True
        if scenario.failure_mode is ResilienceFailureMode.DOMAIN_OUTAGE:
            affected = candidate.domain in affected_domains
        if scenario.failure_mode is ResilienceFailureMode.CASCADING_OUTAGE:
            affected = candidate.resource_id in affected_ids or candidate.domain in affected_domains
        if scenario.failure_mode is ResilienceFailureMode.TELEMETRY_DEGRADATION:
            affected = False
        if scenario.failure_mode is ResilienceFailureMode.CAPACITY_DEGRADATION:
            affected = candidate.resource_id in affected_ids or candidate.domain in affected_domains
            if affected and scenario.capacity_scale is not None:
                update["estimated_capacity_bps"] = (
                    candidate.estimated_capacity_bps * scenario.capacity_scale
                )
        if affected and scenario.failure_mode in {
            ResilienceFailureMode.RESOURCE_OUTAGE,
            ResilienceFailureMode.DOMAIN_OUTAGE,
            ResilienceFailureMode.CASCADING_OUTAGE,
        }:
            update["available"] = False
        degraded.append(candidate.model_copy(deep=True, update=update))
    return degraded


def _verify(
    *,
    selected: UnifiedCandidate | None,
    demand_bps: float,
    event_type: UnifiedHandoverEventType,
    telemetry_gate_open: bool,
) -> tuple[bool, str]:
    if not telemetry_gate_open:
        if event_type in {
            UnifiedHandoverEventType.ATTACH,
            UnifiedHandoverEventType.HANDOVER,
        }:
            return False, "telemetry gate blocked state-changing action"
        return True, "telemetry gate closed; no state-changing action was issued"
    if event_type is UnifiedHandoverEventType.NO_COVERAGE:
        return selected is None, "no-coverage state is consistent"
    if selected is None or not _candidate_available(selected):
        return False, "selected serving resource is unavailable or has zero capacity"
    if selected.estimated_capacity_bps + 1e-9 < demand_bps:
        return False, "selected serving resource cannot satisfy demand"
    return True, "serving resource is available and satisfies demand"


def default_resilience_scenarios() -> tuple[ResilienceScenario, ...]:
    """Return a deterministic campaign spanning single, cross-domain, and telemetry faults."""
    return (
        ResilienceScenario(
            scenario_id="ground-cell-02-outage",
            failure_mode=ResilienceFailureMode.RESOURCE_OUTAGE,
            start_time_s=600.0,
            end_time_s=1200.0,
            affected_resource_ids=("ground-cell-02",),
        ),
        ResilienceScenario(
            scenario_id="uav-01-outage",
            failure_mode=ResilienceFailureMode.RESOURCE_OUTAGE,
            start_time_s=0.0,
            end_time_s=120.0,
            affected_resource_ids=("air-uav-01",),
        ),
        ResilienceScenario(
            scenario_id="ground-domain-isolation",
            failure_mode=ResilienceFailureMode.DOMAIN_OUTAGE,
            start_time_s=1200.0,
            end_time_s=1800.0,
            affected_domains=(NetworkDomain.GROUND,),
        ),
        ResilienceScenario(
            scenario_id="air-domain-isolation",
            failure_mode=ResilienceFailureMode.DOMAIN_OUTAGE,
            start_time_s=1800.0,
            end_time_s=2400.0,
            affected_domains=(NetworkDomain.AIR,),
        ),
        ResilienceScenario(
            scenario_id="telemetry-health-degradation",
            failure_mode=ResilienceFailureMode.TELEMETRY_DEGRADATION,
            start_time_s=600.0,
            end_time_s=1200.0,
            telemetry_health=0.50,
        ),
        ResilienceScenario(
            scenario_id="haps-capacity-collapse",
            failure_mode=ResilienceFailureMode.CAPACITY_DEGRADATION,
            start_time_s=2400.0,
            end_time_s=3000.0,
            affected_resource_ids=("air-haps-01",),
            capacity_scale=0.01,
        ),
        ResilienceScenario(
            scenario_id="full-service-isolation",
            failure_mode=ResilienceFailureMode.CASCADING_OUTAGE,
            start_time_s=2400.0,
            end_time_s=2700.0,
            affected_domains=(
                NetworkDomain.GROUND,
                NetworkDomain.AIR,
                NetworkDomain.SPACE,
            ),
        ),
    )


class ResilienceCampaignEngine:
    """Execute controlled resilience injections over the validated SAG loop."""

    def __init__(self, *, cross_domain: CrossDomainSAGIntegrationEngine | None = None) -> None:
        self._cross_domain = cross_domain or CrossDomainSAGIntegrationEngine()

    def _snapshot(
        self,
        *,
        timestamp_s: float,
        config: ResilienceCampaignConfig,
        evidence_class: CrossDomainSAGEvidence,
    ) -> tuple[UnifiedNetworkSnapshot, str, str]:
        result = self._cross_domain.run(
            [],
            config=CrossDomainSAGConfig(
                reference_time_s=timestamp_s,
                user_demand_bps=config.user_demand_bps,
                timeout_s=config.timeout_s,
                use_real_ephemeris=config.use_real_ephemeris,
            ),
            evidence_class=evidence_class,
        )
        return result.unified_snapshot, result.propagation_model, result.ephemeris_source

    def _run_scenario(
        self,
        scenario: ResilienceScenario,
        *,
        snapshots: dict[float, UnifiedNetworkSnapshot],
        config: ResilienceCampaignConfig,
        baseline_telemetry_health: float,
    ) -> ResilienceScenarioResult:
        controllers: dict[str, UnifiedHandoverController] = {}
        cycles: list[ResilienceCycleResult] = []
        impacted_users: set[str] = set()
        recovery_time_s: float | None = None

        for timestamp_s in config.timestamps_s:
            snapshot = snapshots[timestamp_s]
            failure_active = scenario.start_time_s <= timestamp_s < scenario.end_time_s
            health = (
                scenario.telemetry_health
                if failure_active and scenario.failure_mode is ResilienceFailureMode.TELEMETRY_DEGRADATION
                and scenario.telemetry_health is not None
                else baseline_telemetry_health
            )
            gate_open = health >= config.minimum_telemetry_health
            for association in snapshot.associations:
                candidates = _apply_fault(
                    association.candidates,
                    scenario=scenario,
                    failure_active=failure_active,
                )
                controller = controllers.setdefault(
                    association.user_id,
                    UnifiedHandoverController(
                        policy=UnifiedHandoverPolicy(
                            hysteresis_db=config.handover_hysteresis_db,
                            time_to_trigger_s=config.handover_time_to_trigger_s,
                        )
                    ),
                )
                previous_id = controller.serving_resource_id
                if not gate_open:
                    event_type = (
                        UnifiedHandoverEventType.NO_COVERAGE
                        if previous_id is None
                        else UnifiedHandoverEventType.RETAIN
                    )
                    selected_id = previous_id
                    selected_domain = None
                    decision_reason = "autonomous state-changing action suppressed by telemetry health gate"
                else:
                    event = controller.update(
                        user_id=association.user_id,
                        timestamp_s=timestamp_s,
                        candidates=candidates,
                    )
                    event_type = event.event_type
                    selected_id = event.new_resource_id
                    selected_domain = event.new_domain
                    decision_reason = event.reason

                selected = _candidate_by_id(candidates, controller.serving_resource_id)
                best = _best_available(candidates)
                demand_satisfied = (
                    selected is not None
                    and selected.available
                    and selected.estimated_capacity_bps + 1e-9 >= association.demand_bps
                )
                verification_passed, verification_reason = _verify(
                    selected=selected,
                    demand_bps=association.demand_bps,
                    event_type=event_type,
                    telemetry_gate_open=gate_open,
                )
                if failure_active:
                    affected_candidate_ids = set(scenario.affected_resource_ids)
                    impacted = (
                        scenario.failure_mode is ResilienceFailureMode.DOMAIN_OUTAGE
                        and any(candidate.domain in scenario.affected_domains for candidate in candidates)
                    ) or any(candidate.resource_id in affected_candidate_ids for candidate in candidates)
                    if impacted:
                        impacted_users.add(association.user_id)

                action = {
                    UnifiedHandoverEventType.ATTACH: "attach",
                    UnifiedHandoverEventType.RETAIN: "retain",
                    UnifiedHandoverEventType.HANDOVER: "handover",
                    UnifiedHandoverEventType.NO_COVERAGE: "no_coverage",
                }[event_type]
                cycles.append(
                    ResilienceCycleResult(
                        scenario_id=scenario.scenario_id,
                        timestamp_s=timestamp_s,
                        user_id=association.user_id,
                        failure_active=failure_active,
                        previous_resource_id=previous_id,
                        selected_resource_id=selected_id,
                        selected_domain=selected_domain,
                        best_available_resource_id=None if best is None else best.resource_id,
                        demand_bps=association.demand_bps,
                        selected_capacity_bps=(
                            0.0 if selected is None else selected.estimated_capacity_bps
                        ),
                        demand_satisfied=demand_satisfied,
                        telemetry_health=health,
                        telemetry_gate_open=gate_open,
                        decision_action="blocked" if not gate_open else action,
                        decision_reason=decision_reason,
                        verification_passed=verification_passed,
                        verification_reason=verification_reason,
                    )
                )

        ordered_recovery = sorted(
            {
                cycle.timestamp_s
                for cycle in cycles
                if cycle.timestamp_s >= scenario.end_time_s and cycle.demand_satisfied
                and cycle.verification_passed
            }
        )
        if ordered_recovery:
            candidate_time = ordered_recovery[0]
            user_count = len({cycle.user_id for cycle in cycles})
            recovered_users = {
                cycle.user_id
                for cycle in cycles
                if cycle.timestamp_s == candidate_time
                and cycle.demand_satisfied
                and cycle.verification_passed
            }
            if len(recovered_users) == user_count:
                recovery_time_s = candidate_time

        counts = Counter(cycle.decision_action for cycle in cycles)
        affected_cycles = sum(cycle.failure_active for cycle in cycles)
        verification_pass = sum(cycle.verification_passed for cycle in cycles)
        satisfied = sum(cycle.demand_satisfied for cycle in cycles)
        max_unmet = max(
            (max(0.0, cycle.demand_bps - cycle.selected_capacity_bps) for cycle in cycles),
            default=0.0,
        )
        recovery_latency = (
            None if recovery_time_s is None else max(0.0, recovery_time_s - scenario.end_time_s)
        )
        payload = {
            "scenario": scenario.model_dump(mode="json"),
            "cycles": [cycle.model_dump(mode="json") for cycle in cycles],
            "recovery_time_s": recovery_time_s,
        }
        return ResilienceScenarioResult(
            scenario_id=scenario.scenario_id,
            failure_mode=scenario.failure_mode,
            start_time_s=scenario.start_time_s,
            end_time_s=scenario.end_time_s,
            cycle_count=len(cycles),
            affected_cycle_count=affected_cycles,
            impacted_user_count=len(impacted_users),
            attach_count=counts["attach"],
            handover_count=counts["handover"],
            retain_count=counts["retain"],
            no_coverage_count=counts["no_coverage"],
            blocked_count=counts["blocked"],
            verification_pass_count=verification_pass,
            verification_fail_count=len(cycles) - verification_pass,
            demand_satisfaction_ratio=satisfied / len(cycles) if cycles else 0.0,
            recovery_observed=recovery_time_s is not None,
            recovery_time_s=recovery_time_s,
            recovery_latency_s=recovery_latency,
            max_unmet_demand_bps=max_unmet,
            cycles=tuple(cycles),
            scenario_fingerprint=_fingerprint(payload),
        )

    def run(
        self,
        records: Iterable[TelemetryRecord],
        scenarios: Iterable[ResilienceScenario],
        *,
        config: ResilienceCampaignConfig,
        evidence_class: CrossDomainSAGEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> ResilienceCampaignReport:
        ordered = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
        if not ordered:
            raise ValueError("resilience campaign requires at least one scenario")
        if len({item.scenario_id for item in ordered}) != len(ordered):
            raise ValueError("resilience campaign scenario identifiers must be unique")

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
        baseline_telemetry_health = _telemetry_health(telemetry_report)

        snapshots: dict[float, UnifiedNetworkSnapshot] = {}
        propagation_model = telemetry_result.propagation_model
        ephemeris_source = telemetry_result.ephemeris_source
        for timestamp_s in config.timestamps_s:
            snapshot, propagation_model, ephemeris_source = self._snapshot(
                timestamp_s=timestamp_s,
                config=config,
                evidence_class=evidence_class,
            )
            snapshots[timestamp_s] = snapshot

        results = tuple(
            self._run_scenario(
                scenario,
                snapshots=snapshots,
                config=config,
                baseline_telemetry_health=baseline_telemetry_health,
            )
            for scenario in ordered
        )
        total_cycles = sum(result.cycle_count for result in results)
        total_affected = sum(result.affected_cycle_count for result in results)
        total_verification = sum(result.verification_pass_count for result in results)
        total_satisfied = sum(
            sum(cycle.demand_satisfied for cycle in result.cycles) for result in results
        )
        latencies = [
            result.recovery_latency_s
            for result in results
            if result.recovery_latency_s is not None
        ]
        summary = ResilienceCampaignSummary(
            scenario_count=len(results),
            cycle_count=total_cycles,
            affected_cycle_count=total_affected,
            recovered_scenario_count=sum(result.recovery_observed for result in results),
            unrecovered_scenario_count=sum(not result.recovery_observed for result in results),
            attach_count=sum(result.attach_count for result in results),
            handover_count=sum(result.handover_count for result in results),
            retain_count=sum(result.retain_count for result in results),
            no_coverage_count=sum(result.no_coverage_count for result in results),
            blocked_count=sum(result.blocked_count for result in results),
            verification_pass_count=total_verification,
            verification_fail_count=sum(
                result.verification_fail_count for result in results
            ),
            demand_satisfaction_ratio=total_satisfied / total_cycles if total_cycles else 0.0,
            verification_success_ratio=total_verification / total_cycles if total_cycles else 0.0,
            mean_recovery_latency_s=(sum(latencies) / len(latencies) if latencies else None),
            max_recovery_latency_s=(max(latencies) if latencies else None),
        )
        payload = {
            "telemetry": telemetry_report.model_dump(mode="json"),
            "scenarios": [result.model_dump(mode="json") for result in results],
            "summary": summary.model_dump(mode="json"),
            "propagation_model": propagation_model,
            "ephemeris_source": ephemeris_source,
        }
        return ResilienceCampaignReport(
            evidence_class=evidence_class,
            telemetry_loop=telemetry_report,
            scenarios=results,
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


__all__ = ["ResilienceCampaignEngine", "default_resilience_scenarios"]
