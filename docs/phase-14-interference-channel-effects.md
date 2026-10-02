# Phase 14 — Interference & Channel Effects

## Scope

Phase 14 adds an explicit, deterministic interference and channel-impairment layer on top of
Phase 13. It does not replace the validated Ground, Air, Space, unified, routing, QoS, or
resource-management models.

The new layer models:

- co-channel and partially overlapping-channel interference;
- frequency-band overlap as a bounded power-coupling factor;
- transmitter activity/duty cycle;
- deterministic coupling/isolation losses;
- explicit additional channel loss supplied by the scenario;
- linear-domain aggregation of multiple interferers;
- recomputed SINR, Shannon capacity, link margin, and availability;
- propagation of the degraded candidate state into the existing spectrum scheduler.

## Interference model

For an interferer with transmit power `P_tx`, gains `G_tx` and `G_rx`, free-space path loss
`L_fs`, additional path loss `L_add`, coupling loss `L_c`, overlap fraction `F`, and activity
factor `A`:

`P_rx = P_tx + G_tx + G_rx - L_fs - L_add - L_c`

The effective in-band interference power is evaluated in watts as:

`I = 10^((P_rx-30)/10) × F × A`

Multiple contributors are summed in linear power units before converting back to dBm.

## Channel effects

`ChannelEffectProfile.additional_loss_db` represents an explicit deterministic attenuation
outside the baseline Phase 4 propagation-loss categories. This can represent a scenario-level
shadow/blockage/clutter loss without inventing a stochastic realization.

The desired received power is reduced by the configured channel loss before SINR is recomputed.

## Realism boundary

This is a transparent engineering abstraction, not a complete 3GPP NR PHY implementation.
The phase intentionally does not claim detailed OFDM numerology, MCS tables, HARQ, antenna
array beamforming, spatial correlation, terrain-aware ray tracing, or stochastic fast-fading
traces. Those can be added when the later digital-twin/telemetry/predictive layers require them.

The frequency-overlap model is a bandwidth-overlap approximation. Detailed adjacent-channel
emission masks and receiver selectivity are represented only through configurable coupling loss
at this stage.

## Integration

Phase 14 is additive. Existing candidate measurements remain the baseline. The evaluator produces
an affected copy of a `LinkBudget` or `UnifiedCandidate`, preserving geometry, mobility, and
resource identity while updating received power, SINR, capacity, margin, and availability.

This degraded state can be passed into Phase 13's `schedule_spectrum` function so spectrum
allocation responds to actual interference-impaired capacity rather than an idealized baseline.

## Validation

The phase includes tests for:

- full-band and non-overlapping frequency cases;
- linear-domain interference aggregation;
- deterministic channel-loss degradation;
- candidate availability loss under strong interference;
- inactive-interferer baseline preservation.
