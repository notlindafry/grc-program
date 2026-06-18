# Methodology

This document pins the quantitative choices so they are consistent across every
computation and reproducible from the same corpus. If you change one, change it
here.

## A light, domain-neutral adaptation of FAIR

The model is a deliberately light adaptation, loosely inspired by FAIR's
frequency-times-magnitude decomposition, generalized so non-adversarial tech
risks (outages, data integrity) sit in the same model as adversarial ones
(account takeover, data exfiltration). It borrows FAIR's shape, not its rigor:
the lineage is intentional and kept visible, and the adaptation (two
domain-neutral frequency-side variables) is the point. The tool does not claim
conformance to the FAIR standard.

Risk is three estimated variables, each a 90% confidence interval:

- **Opportunity Frequency (OF)**: how many times a year a condition arises that
  could produce this loss. Environmental. (A threat contact for an adversarial
  risk; a disruption, a deploy, or a risky write for a non-adversarial one.)
- **Probability of Realization (PoR)**: given that condition, the chance the
  loss event is actually realized. Control failure is folded into this variable
  on purpose, so a preventive-control gap has a clean home. This generalizes
  FAIR's "probability the actor acts **and succeeds**": for an outage it is the
  chance a disruption becomes customer-facing; for data integrity, the chance a
  bad write corrupts downstream. PoR therefore does not carry FAIR's strict
  canonical meaning of the actor's decision alone, a deliberate and documented
  simplification.
- **Loss Magnitude (LM)**: loss in dollars if the loss event occurs.

```
LEF = OF × PoR        (Loss Event Frequency: how often the loss event happens)
ALE = LEF × LM        (Annual Loss Exposure)
```

Loss Event Frequency and Loss Magnitude are unchanged from FAIR and already read
neutrally. An exception moves exactly one variable and supplies its new 90% CI.

## Calibrated estimation is the foundation

The whole system rests on the ranges being honest. Untrained estimators are
reliably overconfident: their stated 90% interval captures the truth far less
than 90% of the time, so ranges come out too narrow and every downstream number
inherits the error. Calibration training corrects this cheaply.

The tool treats calibration as a hard gate. Each estimate records `estimated_by`;
the tool resolves that against `estimators.yaml`. An estimate from someone
uncalibrated, unknown, or whose calibration is older than the refresh window
(default 365 days, measured against the run's `--as-of` date) is flagged
low-confidence and kept out of every trusted band. The tool never launders a
weak input into a confident output.

## Distributions

Each 90% CI `[low, high]` is read as the **5th and 95th percentiles**. A 90%
interval spans ±`Z95` standard deviations of the transformed-space mean, where
`Z95 = 1.6448536269514722`.

| Variable | Family | Why |
|---|---|---|
| OF, LM | **lognormal** | positive, right-skewed, multiplicative; parameters solved in log space |
| PoR | **logit-normal** | naturally bounded to `(0, 1)`; fit symmetrically in logit space, the same way the lognormal is fit in log space |

Fitting (lognormal, in log space): `μ = (ln low + ln high) / 2`,
`σ = (ln high − ln low) / (2·Z95)`. Logit-normal is identical with
`logit(p) = ln(p / (1 − p))` in place of `ln`. The logit-normal avoids the
truncation artefacts of a clipped normal and behaves well even for the small
probabilities typical of PoR.

## Monte Carlo

- **Iterations:** 10,000 by default (`--iterations`). Enough for stable 5th/95th
  percentiles; the fidelity per line is deliberately rough.
- **Seed:** fixed (default `20260617`, `--seed`). This is a git-native audit
  tool, so the same corpus must produce the same report. Streams are seeded by a
  deterministic string key per entity, which is independent across entities,
  stable across processes, and independent of evaluation order.
- **Never collapse to a point.** Every user-facing figure is a band (5th–95th)
  or a relative comparison. The mean is computed only as a ranking key and is
  never rendered alone. The one single figure the tool prints is an
  `appetite_threshold`: a stated input the organization chose, not an estimate.

### Baseline ALE per risk

Monte Carlo over `OF × PoR × LM` using the risk's baseline ranges.

### Exception contribution

The marginal residual a single exception adds. Per iteration:

```
contribution = ALE(moved variable swapped to with_exception) − ALE(all baseline)
```

computed under **common random numbers**: one scenario per iteration fixes the
unmoved variables *and* the standardized position of the moved variable on both
sides. The contribution is then purely the loss added by shifting that one
variable's distribution from baseline to its with-exception range.

We pair the moved variable's two evaluations (same standardized draw) rather than
drawing them independently. This isolates the exception's marginal effect (the
whole point) and removes the Monte Carlo artefact where two close,
independently-drawn estimates of the same variable produce a spuriously negative
"contribution" in the lower tail. The band keeps its width from the unmoved
variables and from where the shared scenario lands, so uncertainty is preserved.

### Current residual per risk

Baseline ALE plus the summed contributions of the risk's **active, trusted**
exceptions. Contributions are summed as **independent marginal estimates** by
adding their sample streams element-wise. Real effects can interact; this is a
deliberate light-fidelity simplification, stated plainly rather than hidden.

Trust-flagged exceptions (uncalibrated/stale estimator, vague scope) are excluded
from the residual and reported separately. Action-flagged exceptions (no plan, no
diversion destination) are included: their number is trustworthy even though the
record is not actionable.

### Appetite state

Compare the residual band to `appetite_threshold`:

- **over**: the whole band sits above the line (`p5 ≥ threshold`).
- **within**: the whole band sits below it (`p95 ≤ threshold`).
- **straddling**: the band crosses it. Probabilistic, never binary.

## Breach classification

For an over/straddling risk, the active trusted contributors are ranked by
expected contribution and the breach is classified by three rules applied in
order. "Contributed exposure" is the sum of contributor means (the exposure
added over baseline), so a contributor's *share* is its mean divided by that sum.

1. **Solo-breach rule** *(structural; no threshold)*. If baseline plus any single
   contributor alone is `over` appetite (its standalone 90% residual band sits
   fully above the line), that exception is sufficient by itself. The breach is
   **single-acceptance** and the culprit is the largest such exception. This uses
   the same 90%-band appetite test (`p5 ≥ threshold`) as everything else, so it
   needs no tunable of its own.

2. **Dominant-share threshold** = `single_acceptance_share`, **default 0.50**,
   range `(0, 1]`. If no exception breaches alone but the leading contributor's
   share is ≥ this value, the breach is **single-acceptance** (culprit = the top
   contributor). At 0.50 the lead must be the majority of the added exposure.
   Raise it to demand a more dominant culprit before blaming one decision; lower
   it to call more breaches single-acceptance.

3. **Accumulation** *(otherwise)*. No single sufficient cause and the exposure is
   spread across many calls. This is the death-by-a-thousand-cuts pattern: a
   process problem with no individual to send it back to.

The tool also reports, per contributor, whether that exception alone (baseline +
just it) would be over: the "tolerable on its own" signal that makes an
accumulation breach legible, and `all_tolerable_alone`, true when *every*
contributor stays within appetite on its own.

`single_acceptance_share` is set under `breach:` in `config.yaml`, or with
`--single-acceptance-share` on the CLI (the flag overrides the file). The
over/straddling/within boundaries themselves are **not** tunable: they are fixed
by the 90% band (5th/95th percentiles) by design, since the SPEC mandates a 90%
CI everywhere.

## Remediations and post-remediation

A remediation is a static, version-controlled record of work that reduces risk.
There is no scheduling or workflow: it is filed and reviewed like any other
record and carries a `status`. Only **funded** and **in_progress** remediations
are projected into the post-remediation figures; a **proposed** one is carried
but never counted, so a projection never credits work nobody has committed to. A
remediation does exactly one thing:

- **restore** returns a control's accepted exceptions to baseline. Every active
  exception on `restores_control` is dropped from the residual, so the control's
  whole cluster contribution clears. It models a gap being closed.
- **strengthen** moves one factor of one `mapped_risk` to an explicit, better
  90% CI (`post_control_90ci`), not back to baseline. The factor named by
  `moves` is re-fit to that CI and the risk recomputed. That CI is
  calibration-gated through `estimated_by`, exactly like an exception's, so a
  strengthen cannot launder an uncalibrated number either.

**Post-remediation residual** is the projected residual once a risk's funded
remediations land. Composition is **first-order**: restores clear their clusters
and strengthens swap their one factor, then the risk is recomputed once. We do
not model second-round interactions between remediations. Like the rest of the
tool this is a deliberate light-fidelity simplification, stated rather than
hidden.

**Risk reduction**, the number the ranked list sorts on, is the dollars an
action buys down, as a band:

- For a **restore** it is the cleared cluster's residual contribution: the
  exposure that disappears when those exceptions return to baseline.
- For a **strengthen** it is current-minus-projected for that risk, computed
  under **common random numbers** so the difference is the genuine effect of
  re-fitting the one factor and not Monte Carlo noise between two runs.

The portfolio "2026 risk exposure" arc reads the same machinery at three points:
the book entering the year (only exceptions filed before the year start, no
remediations applied), the book today (current residual), and the book exiting
the year if the funded plan lands (post-remediation residual). The three bands
are relative magnitudes and do not add to a to-the-dollar waterfall.

## Clustering and the ranked list

"What to fix first" ranks the work that moves quantified risk by the **risk
reduction** each action buys down, not by raw residual size. Two kinds of row
share the one ranking:

- **Funded remediations** (`funded` or `in_progress`), whose reduction is
  defined above.
- **Unfunded breaching clusters.** Exceptions still grouped by **control** (the
  deviated-from control is the root cause; a singleton cluster renders as the
  individual exception), filtered to the action layer: clusters that push a risk
  over/straddling, plus any whose **upper bound alone** would breach even when
  the expected value does not (the tail-risk catch). For a cluster the reduction
  is its own residual contribution, since clearing the exceptions is the lever.
  Clusters comfortably within appetite are real accepted risk but are not "fix
  first"; they surface in the drift view.

The two are **deduplicated**: when a funded `restore` already covers a cluster's
control, the remediation row stands in for it and the cluster is not listed
again. Rows are then ordered by the mean of the risk-reduction band (the mean is
a sort key only and is never rendered alone).

A cluster's action payload (`mechanism`, `reduces`, deadline, `owner`) is taken
from its well-formed members. Action-flagged members are counted in the
cluster's residual (the risk is real) but are pulled out and listed in the
send-back bucket to be re-assessed first.

## Drift

An OKR (an Objective plus Key Results) has two footprints, reported separately
and combined:

- **Internal**: exceptions filed against the OKR (`okr == X`), accepting debt on
  its own risks.
- **External**: exceptions filed against other OKRs that name this one in
  `diverted_to`, raising *those* OKRs' risks. Invisible on the OKR's own ledger;
  it surfaces only by reading the whole corpus.

The view displays the OKR's key results as the commitments the footprint is
eroding. The trajectory is time-aware: it compares the first-quarter filing count
to the count in the final stretch before the `period_end` (default 8 weeks), and
flags acceleration into a deadline: the tell.
