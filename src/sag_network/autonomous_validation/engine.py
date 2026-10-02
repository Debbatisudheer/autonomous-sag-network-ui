from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from pydantic import BaseModel

from sag_network.closed_loop_autonomy import ClosedLoopAutonomyConfig, ClosedLoopAutonomyEngine
from sag_network.cross_domain_sag import (
    CrossDomainSAGConfig,
    CrossDomainSAGEvidence,
    CrossDomainSAGIntegrationEngine,
)
from sag_network.resilience_campaign import (
    ResilienceCampaignConfig,
    ResilienceCampaignEngine,
    default_resilience_scenarios,
)
from sag_network.telemetry.models import TelemetryRecord

from .models import (
    AutonomousValidationConfig,
    AutonomousValidationReport,
    AutonomousValidationSummary,
    ValidationCheck,
    ValidationPhaseEvidence,
    ValidationStatus,
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


def _logical_report_fingerprint(report: BaseModel, *, phase: str) -> str:
    if phase == "77":
        payload = report.model_dump(mode="json")
        payload.pop("telemetry_loop", None)
        payload.pop("integration_fingerprint", None)
        return _fingerprint(payload)
    if phase == "78":
        payload = report.model_dump(mode="json")
        payload.pop("telemetry_loop", None)
        payload.pop("integration_fingerprint", None)
        return _fingerprint(payload)
    if phase == "76":
        payload = report.model_dump(mode="json")
        payload.pop("telemetry_loop", None)
        payload.pop("integration_fingerprint", None)
        return _fingerprint(payload)
    raise ValueError(f"unsupported validation phase: {phase}")


def _check(
    *,
    check_id: str,
    phase: str,
    condition: bool,
    observed: object,
    expected: object,
    detail: str,
) -> ValidationCheck:
    status = ValidationStatus.PASS if condition else ValidationStatus.FAIL
    payload = {
        "check_id": check_id,
        "phase": phase,
        "status": status,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ValidationCheck(
        check_id=check_id,
        phase=phase,
        status=status,
        observed=str(observed),
        expected=str(expected),
        detail=detail,
        fingerprint=_fingerprint(payload),
    )


class AutonomousSAGValidationEngine:
    """Validate the integrated Phase 76–78 autonomous SAG control boundary."""

    def __init__(
        self,
        *,
        cross_domain: CrossDomainSAGIntegrationEngine | None = None,
        autonomy: ClosedLoopAutonomyEngine | None = None,
        resilience: ResilienceCampaignEngine | None = None,
    ) -> None:
        self._cross_domain = cross_domain or CrossDomainSAGIntegrationEngine()
        self._autonomy = autonomy or ClosedLoopAutonomyEngine(cross_domain=self._cross_domain)
        self._resilience = resilience or ResilienceCampaignEngine(cross_domain=self._cross_domain)

    def run(
        self,
        records: Iterable[TelemetryRecord],
        *,
        config: AutonomousValidationConfig,
        evidence_class: CrossDomainSAGEvidence,
        source_sha256: str = "",
        provenance_verified: bool = False,
    ) -> AutonomousValidationReport:
        record_list = list(records)
        final_time = config.timestamps_s[-1]

        phase76 = self._cross_domain.run(
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
        phase77_config = ClosedLoopAutonomyConfig(
            timestamps_s=config.timestamps_s,
            user_demand_bps=config.user_demand_bps,
            use_real_ephemeris=config.use_real_ephemeris,
            use_udp_loopback=config.use_udp_loopback,
            timeout_s=config.timeout_s,
            minimum_telemetry_health=config.minimum_telemetry_health,
            handover_hysteresis_db=config.handover_hysteresis_db,
            handover_time_to_trigger_s=config.handover_time_to_trigger_s,
        )
        phase77 = self._autonomy.run(
            record_list,
            config=phase77_config,
            evidence_class=evidence_class,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )
        phase78 = self._resilience.run(
            record_list,
            default_resilience_scenarios(),
            config=ResilienceCampaignConfig(
                timestamps_s=config.timestamps_s,
                user_demand_bps=config.user_demand_bps,
                use_real_ephemeris=config.use_real_ephemeris,
                use_udp_loopback=config.use_udp_loopback,
                timeout_s=config.timeout_s,
                minimum_telemetry_health=config.minimum_telemetry_health,
                handover_hysteresis_db=config.handover_hysteresis_db,
                handover_time_to_trigger_s=config.handover_time_to_trigger_s,
            ),
            evidence_class=evidence_class,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )

        phase77_repeat = self._autonomy.run(
            record_list,
            config=phase77_config,
            evidence_class=evidence_class,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )
        phase78_repeat = self._resilience.run(
            record_list,
            default_resilience_scenarios(),
            config=ResilienceCampaignConfig(
                timestamps_s=config.timestamps_s,
                user_demand_bps=config.user_demand_bps,
                use_real_ephemeris=config.use_real_ephemeris,
                use_udp_loopback=config.use_udp_loopback,
                timeout_s=config.timeout_s,
                minimum_telemetry_health=config.minimum_telemetry_health,
                handover_hysteresis_db=config.handover_hysteresis_db,
                handover_time_to_trigger_s=config.handover_time_to_trigger_s,
            ),
            evidence_class=evidence_class,
            source_sha256=source_sha256,
            provenance_verified=provenance_verified,
        )

        deterministic = (
            _logical_report_fingerprint(phase76, phase="76")
            == _logical_report_fingerprint(
                self._cross_domain.run(
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
                ),
                phase="76",
            )
            and _logical_report_fingerprint(phase77, phase="77")
            == _logical_report_fingerprint(phase77_repeat, phase="77")
            and _logical_report_fingerprint(phase78, phase="78")
            == _logical_report_fingerprint(phase78_repeat, phase="78")
        )
        phase_evidence = (
            ValidationPhaseEvidence(
                phase="76",
                name="Cross-Domain SAG Network",
                status=ValidationStatus.PASS if phase76.status == "pass" else ValidationStatus.FAIL,
                evidence_class=evidence_class,
                integration_fingerprint=phase76.integration_fingerprint,
                source_sha256=phase76.source_sha256,
                provenance_verified=phase76.provenance_verified,
                key_metrics={
                    "coverage_ratio": phase76.summary.coverage_ratio,
                    "total_candidate_count": float(phase76.summary.total_candidate_count),
                    "total_user_count": float(phase76.summary.total_user_count),
                },
                network_mutation=phase76.network_mutation,
                hardware_measurement=phase76.hardware_measurement,
            ),
            ValidationPhaseEvidence(
                phase="77",
                name="Real Closed-Loop Autonomy",
                status=ValidationStatus.PASS if phase77.status == "pass" else ValidationStatus.FAIL,
                evidence_class=evidence_class,
                integration_fingerprint=phase77.integration_fingerprint,
                source_sha256=phase77.source_sha256,
                provenance_verified=phase77.provenance_verified,
                key_metrics={
                    "demand_satisfaction_ratio": phase77.summary.demand_satisfaction_ratio,
                    "verification_success_ratio": (
                        phase77.summary.verification_pass_count / phase77.summary.cycle_count
                        if phase77.summary.cycle_count
                        else 0.0
                    ),
                    "handover_count": float(phase77.summary.handover_count),
                },
                network_mutation=phase77.network_mutation,
                hardware_measurement=phase77.hardware_measurement,
            ),
            ValidationPhaseEvidence(
                phase="78",
                name="Real-World Resilience Campaign",
                status=ValidationStatus.PASS if phase78.status == "pass" else ValidationStatus.FAIL,
                evidence_class=evidence_class,
                integration_fingerprint=phase78.integration_fingerprint,
                source_sha256=phase78.source_sha256,
                provenance_verified=phase78.provenance_verified,
                key_metrics={
                    "recovery_ratio": (
                        phase78.summary.recovered_scenario_count / phase78.summary.scenario_count
                        if phase78.summary.scenario_count
                        else 0.0
                    ),
                    "demand_satisfaction_ratio": phase78.summary.demand_satisfaction_ratio,
                    "verification_success_ratio": phase78.summary.verification_success_ratio,
                },
                network_mutation=phase78.network_mutation,
                hardware_measurement=phase78.hardware_measurement,
            ),
        )

        checks = (
            _check(
                check_id="phase76-coverage",
                phase="76",
                condition=phase76.summary.coverage_ratio == 1.0,
                observed=phase76.summary.coverage_ratio,
                expected=1.0,
                detail="Cross-domain baseline must cover the complete configured user population.",
            ),
            _check(
                check_id="phase76-candidate-population",
                phase="76",
                condition=(
                    phase76.summary.total_user_count == 3
                    and phase76.summary.total_candidate_count == 15
                ),
                observed=f"users={phase76.summary.total_user_count}, candidates={phase76.summary.total_candidate_count}",
                expected="users=3, candidates=15",
                detail="The validation uses the established three-user, five-candidates-per-user SAG fixture.",
            ),
            _check(
                check_id="phase77-demand-satisfaction",
                phase="77",
                condition=phase77.summary.demand_satisfaction_ratio == 1.0,
                observed=phase77.summary.demand_satisfaction_ratio,
                expected=1.0,
                detail="Closed-loop autonomy must satisfy configured demand across every simulated cycle.",
            ),
            _check(
                check_id="phase77-verification",
                phase="77",
                condition=phase77.summary.verification_fail_count == 0,
                observed=phase77.summary.verification_fail_count,
                expected=0,
                detail="Every Phase 77 action must pass the existing post-action verification boundary.",
            ),
            _check(
                check_id="phase78-recovery",
                phase="78",
                condition=phase78.summary.recovered_scenario_count == phase78.summary.scenario_count,
                observed=f"{phase78.summary.recovered_scenario_count}/{phase78.summary.scenario_count}",
                expected=f"{phase78.summary.scenario_count}/{phase78.summary.scenario_count}",
                detail="Each bounded resilience scenario must demonstrate observed recovery within the campaign horizon.",
            ),
            _check(
                check_id="phase78-evidence-retention",
                phase="78",
                condition=(
                    phase78.summary.verification_fail_count > 0
                    or phase78.summary.no_coverage_count > 0
                    or phase78.summary.blocked_count > 0
                ),
                observed=(
                    f"verification_fail={phase78.summary.verification_fail_count}, "
                    f"no_coverage={phase78.summary.no_coverage_count}, "
                    f"blocked={phase78.summary.blocked_count}"
                ),
                expected="at least one non-ideal resilience outcome retained",
                detail="The campaign must expose degradation outcomes rather than hide all injected impact.",
            ),
            _check(
                check_id="deterministic-repeatability",
                phase="79",
                condition=deterministic,
                observed=deterministic,
                expected=True,
                detail="Repeated Phase 77 and Phase 78 executions must reproduce their integration fingerprints.",
            ),
            _check(
                check_id="evidence-boundary",
                phase="79",
                condition=all(
                    not item.network_mutation and not item.hardware_measurement
                    for item in phase_evidence
                ),
                observed=str(
                    [
                        {
                            "phase": item.phase,
                            "network_mutation": item.network_mutation,
                            "hardware_measurement": item.hardware_measurement,
                        }
                        for item in phase_evidence
                    ]
                ),
                expected="all false",
                detail="Validation confirms no external network mutation or physical hardware measurement is silently claimed.",
            ),
            _check(
                check_id="provenance-boundary",
                phase="79",
                condition=(
                    evidence_class is not CrossDomainSAGEvidence.PUBLIC_DATA
                    or (bool(phase78.source_sha256) and phase78.provenance_verified)
                ),
                observed=f"source_sha256_present={bool(phase78.source_sha256)}, provenance_verified={phase78.provenance_verified}",
                expected=(
                    "verified public source SHA-256" if evidence_class is CrossDomainSAGEvidence.PUBLIC_DATA
                    else "provenance requirement not applicable"
                ),
                detail="Public-data validation requires preserved source provenance; synthetic/local modes remain explicitly non-public evidence.",
            ),
        )

        passed = sum(check.status is ValidationStatus.PASS for check in checks)
        failed = len(checks) - passed
        phase78_recovery_ratio = (
            phase78.summary.recovered_scenario_count / phase78.summary.scenario_count
            if phase78.summary.scenario_count
            else 0.0
        )
        phase77_verification_ratio = (
            phase77.summary.verification_pass_count / phase77.summary.cycle_count
            if phase77.summary.cycle_count
            else 0.0
        )
        boundary_clean = all(
            not item.network_mutation and not item.hardware_measurement for item in phase_evidence
        )
        summary = AutonomousValidationSummary(
            check_count=len(checks),
            passed_check_count=passed,
            failed_check_count=failed,
            phase_count=3,
            phase_76_coverage_ratio=phase76.summary.coverage_ratio,
            phase_77_demand_satisfaction_ratio=phase77.summary.demand_satisfaction_ratio,
            phase_77_verification_success_ratio=phase77_verification_ratio,
            phase_78_recovery_ratio=phase78_recovery_ratio,
            phase_78_verification_success_ratio=phase78.summary.verification_success_ratio,
            deterministic_repeatability=deterministic,
            evidence_boundary_clean=boundary_clean,
        )
        payload = {
            "phase_evidence": [item.model_dump(mode="json") for item in phase_evidence],
            "checks": [item.model_dump(mode="json") for item in checks],
            "summary": summary.model_dump(mode="json"),
        }
        return AutonomousValidationReport(
            status=ValidationStatus.PASS if failed == 0 else ValidationStatus.FAIL,
            evidence_class=evidence_class,
            phase_evidence=phase_evidence,
            checks=checks,
            summary=summary,
            integration_fingerprint=_fingerprint(payload),
            source_sha256=phase78.source_sha256 or phase77.source_sha256 or phase76.source_sha256,
            provenance_verified=(
                phase78.provenance_verified
                or phase77.provenance_verified
                or phase76.provenance_verified
            ),
            propagation_model=phase78.propagation_model,
            ephemeris_source=phase78.ephemeris_source,
            external_network_used=any(
                report.external_network_used for report in (phase76, phase77, phase78)
            ),
            network_mutation=any(item.network_mutation for item in phase_evidence),
            hardware_measurement=any(item.hardware_measurement for item in phase_evidence),
        )


__all__ = ["AutonomousSAGValidationEngine"]
