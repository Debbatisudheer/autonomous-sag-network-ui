from __future__ import annotations

import math

from sag_network.domain.link import LinkBudget
from sag_network.domain.unified import UnifiedCandidate
from sag_network.interference.model import (
    ChannelEffectProfile,
    InterferenceContribution,
    InterferenceEvaluation,
    InterferenceSource,
)
from sag_network.physics.link_budget import (
    free_space_path_loss_db,
    shannon_capacity_bps,
    sinr_db,
)


def _dbm_to_watts(power_dbm: float) -> float:
    return float(math.pow(10.0, (power_dbm - 30.0) / 10.0))


def _watts_to_dbm(power_w: float) -> float:
    if power_w <= 0:
        raise ValueError("power_w must be positive")
    return 10.0 * math.log10(power_w / 1e-3)


def frequency_overlap_fraction(
    *,
    desired_frequency_hz: float,
    desired_bandwidth_hz: float,
    interferer_frequency_hz: float,
    interferer_bandwidth_hz: float,
) -> float:
    """Return the fraction of the desired receiver band occupied by an interferer."""
    if desired_frequency_hz <= 0 or desired_bandwidth_hz <= 0:
        raise ValueError("desired frequency and bandwidth must be positive")
    if interferer_frequency_hz <= 0 or interferer_bandwidth_hz <= 0:
        raise ValueError("interferer frequency and bandwidth must be positive")

    desired_low = desired_frequency_hz - desired_bandwidth_hz / 2.0
    desired_high = desired_frequency_hz + desired_bandwidth_hz / 2.0
    interferer_low = interferer_frequency_hz - interferer_bandwidth_hz / 2.0
    interferer_high = interferer_frequency_hz + interferer_bandwidth_hz / 2.0
    overlap_hz = max(0.0, min(desired_high, interferer_high) - max(desired_low, interferer_low))
    return min(max(overlap_hz / desired_bandwidth_hz, 0.0), 1.0)


def interference_contribution_watts(
    *,
    source: InterferenceSource,
    desired_frequency_hz: float,
    desired_bandwidth_hz: float,
) -> tuple[float, InterferenceContribution]:
    """Calculate one interferer's effective in-band received power."""
    overlap = frequency_overlap_fraction(
        desired_frequency_hz=desired_frequency_hz,
        desired_bandwidth_hz=desired_bandwidth_hz,
        interferer_frequency_hz=source.carrier_frequency_hz,
        interferer_bandwidth_hz=source.bandwidth_hz,
    )
    path_loss_db = free_space_path_loss_db(source.distance_m, source.carrier_frequency_hz)
    received_dbm = (
        source.tx_power_dbm
        + source.tx_gain_dbi
        + source.rx_gain_dbi
        - path_loss_db
        - source.additional_path_loss_db
        - source.coupling_loss_db
    )
    if not source.active or source.activity_factor == 0.0 or overlap == 0.0:
        return 0.0, InterferenceContribution(
            source_id=source.source_id,
            overlap_fraction=overlap,
            received_power_dbm=received_dbm,
            effective_power_dbm=None,
        )

    effective_w = _dbm_to_watts(received_dbm) * overlap * source.activity_factor
    effective_dbm = _watts_to_dbm(effective_w)
    return effective_w, InterferenceContribution(
        source_id=source.source_id,
        overlap_fraction=overlap,
        received_power_dbm=received_dbm,
        effective_power_dbm=effective_dbm,
    )


def evaluate_interference(
    *,
    desired_rx_power_dbm: float,
    noise_power_dbm: float,
    baseline_sinr_db: float,
    desired_frequency_hz: float,
    desired_bandwidth_hz: float,
    interferers: list[InterferenceSource],
) -> InterferenceEvaluation:
    """Aggregate active in-band interference and derive degraded SINR/capacity."""
    total_interference_w = 0.0
    contributions: list[InterferenceContribution] = []
    for source in sorted(interferers, key=lambda item: item.source_id):
        contribution_w, contribution = interference_contribution_watts(
            source=source,
            desired_frequency_hz=desired_frequency_hz,
            desired_bandwidth_hz=desired_bandwidth_hz,
        )
        total_interference_w += contribution_w
        contributions.append(contribution)

    aggregate_interference_dbm = (
        _watts_to_dbm(total_interference_w) if total_interference_w > 0 else None
    )
    degraded_sinr_db = sinr_db(
        desired_rx_power_dbm,
        noise_power_dbm,
        aggregate_interference_dbm,
    )
    capacity_bps = shannon_capacity_bps(desired_bandwidth_hz, degraded_sinr_db)
    return InterferenceEvaluation(
        desired_rx_power_dbm=desired_rx_power_dbm,
        noise_power_dbm=noise_power_dbm,
        aggregate_interference_power_dbm=aggregate_interference_dbm,
        sinr_db=degraded_sinr_db,
        shannon_capacity_bps=capacity_bps,
        interference_degradation_db=baseline_sinr_db - degraded_sinr_db,
        contributions=contributions,
    )


def apply_channel_effects_to_link(
    *,
    link: LinkBudget,
    channel_effects: ChannelEffectProfile,
    interferers: list[InterferenceSource],
) -> LinkBudget:
    """Apply deterministic channel loss and interference to an existing validated link budget."""
    if channel_effects.additional_loss_db == 0.0 and not any(
        source.active and source.activity_factor > 0.0
        and frequency_overlap_fraction(
            desired_frequency_hz=link.frequency_hz,
            desired_bandwidth_hz=link.bandwidth_hz,
            interferer_frequency_hz=source.carrier_frequency_hz,
            interferer_bandwidth_hz=source.bandwidth_hz,
        ) > 0.0
        for source in interferers
    ):
        return link.model_copy(update={"interference_power_dbm": None})

    desired_rx_power_dbm = link.rx_power_dbm - channel_effects.additional_loss_db
    evaluation = evaluate_interference(
        desired_rx_power_dbm=desired_rx_power_dbm,
        noise_power_dbm=link.noise_power_dbm,
        baseline_sinr_db=link.sinr_db,
        desired_frequency_hz=link.frequency_hz,
        desired_bandwidth_hz=link.bandwidth_hz,
        interferers=interferers,
    )
    total_additional_loss_db = link.additional_path_loss_db + channel_effects.additional_loss_db
    total_path_loss_db = link.total_path_loss_db + channel_effects.additional_loss_db
    margin_db = evaluation.sinr_db - link.required_sinr_db
    return link.model_copy(
        update={
            "additional_path_loss_db": total_additional_loss_db,
            "total_path_loss_db": total_path_loss_db,
            "rx_power_dbm": evaluation.desired_rx_power_dbm,
            "interference_power_dbm": evaluation.aggregate_interference_power_dbm,
            "sinr_db": evaluation.sinr_db,
            "shannon_capacity_bps": evaluation.shannon_capacity_bps,
            "link_margin_db": margin_db,
            "available": link.available and margin_db >= 0.0,
        }
    )


def apply_channel_effects_to_candidate(
    *,
    candidate: UnifiedCandidate,
    carrier_frequency_hz: float,
    bandwidth_hz: float,
    required_sinr_db: float,
    channel_effects: ChannelEffectProfile,
    interferers: list[InterferenceSource],
) -> UnifiedCandidate:
    """Apply channel/interference effects to an existing unified candidate measurement."""
    if carrier_frequency_hz <= 0 or bandwidth_hz <= 0:
        raise ValueError("carrier_frequency_hz and bandwidth_hz must be positive")

    if channel_effects.additional_loss_db == 0.0 and not any(
        source.active and source.activity_factor > 0.0
        and frequency_overlap_fraction(
            desired_frequency_hz=carrier_frequency_hz,
            desired_bandwidth_hz=bandwidth_hz,
            interferer_frequency_hz=source.carrier_frequency_hz,
            interferer_bandwidth_hz=source.bandwidth_hz,
        ) > 0.0
        for source in interferers
    ):
        return candidate.model_copy()

    desired_rx_power_dbm = candidate.rx_power_dbm - channel_effects.additional_loss_db
    evaluation = evaluate_interference(
        desired_rx_power_dbm=desired_rx_power_dbm,
        noise_power_dbm=candidate.noise_power_dbm,
        baseline_sinr_db=candidate.sinr_db,
        desired_frequency_hz=carrier_frequency_hz,
        desired_bandwidth_hz=bandwidth_hz,
        interferers=interferers,
    )
    margin_db = evaluation.sinr_db - required_sinr_db
    if candidate.shannon_capacity_bps > 0:
        capacity_efficiency = candidate.estimated_capacity_bps / candidate.shannon_capacity_bps
    else:
        capacity_efficiency = 0.0
    estimated_capacity_bps = evaluation.shannon_capacity_bps * max(min(capacity_efficiency, 1.0), 0.0)

    return candidate.model_copy(
        update={
            "rx_power_dbm": desired_rx_power_dbm,
            "sinr_db": evaluation.sinr_db,
            "link_margin_db": margin_db,
            "shannon_capacity_bps": evaluation.shannon_capacity_bps,
            "estimated_capacity_bps": estimated_capacity_bps,
            "available": candidate.available and margin_db >= 0.0,
        }
    )
