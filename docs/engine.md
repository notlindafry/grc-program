# GRC ecosystem — engine (Day 2)

The engine (`risk_ledger/graph_engine.py`) turns the derived graph into the
numbers the dashboard reads. It **reuses the existing FAIR-shaped Monte Carlo
(`montecarlo.py`) unchanged** — no new quantification engine — and adds only the
aggregation, appetite, banding, and control-health logic. See it with:

```bash
risk-ledger --as-of 2026-06-18 portfolio
```

Four rules from build spec §4 govern everything below.

## 1. One path into residual

Only **factor-moving** issues change residual: an `exception` moves exactly one
scenario factor (OF, PoR, or LM) and its marginal contribution is added under
common random numbers, exactly as in the legacy engine. (A won't-fix accepted
vulnerability is an exception with `reason: accepted_vulnerability`; the
separate `vuln` type was retired in v4.0 §0.0.) A `finding`
carries a bounded severity that feeds **control health and the narrative** but is
never simulated — `IssueRecord.moves_a_factor` is `False` for a finding, so it
can never become a contributor. Control health, evidence freshness, and KRIs
likewise inform the estimate but never add a term.

Issue → scenario is many-to-many; the **first mapped scenario is primary** for
rollup attribution (spec §3), so a factor-moving issue contributes to its primary
scenario only and is never double-counted. A migrated legacy exception still
names a `mapped_risk`; the engine resolves it through the scenario's
`legacy_risk` bridge.

## 2. Aggregation up the tree

The baseline anchors at Tier 3. Residual sample streams sum up the tree using the
Monte Carlo's `sum_streams` (correct band combination, not band arithmetic):

```
scenario residual = baseline ALE + Σ trusted factor-moving contributions
named-risk residual = Σ residual of its MANAGED scenarios
domain residual     = Σ residual of its named risks          (monitored; no ceiling)
portfolio residual  = Σ residual of all MANAGED scenarios
```

Trust handling is inherited: an uncalibrated or stale estimate is computed for
visibility but held **out** of the band (`counts_in_bands`).

## 3. Two-sided appetite banding (RAG)

Appetite is a target, not a ceiling.
`rag_band(mean, threshold, p_exceed, *, floor, p_red)` returns one of three
states, applied to the **managed, calibrated set only**. Three gates, evaluated
in order (SPEC v2.6 §1); the first that fires decides the colour:

| Gate | Test | Result |
|---|---|---|
| **0 — position (ceiling)** | `mean >= threshold` | `over` (red). Expected loss at or past declared tolerance **is** the breach; appetite is a statement about expected annual loss, so this is not a probability question. |
| **1 — danger** | `p_exceed >= p_red` (default 0.33) | `over` (red). A reasonably probable breach is the actionable fact regardless of the mean. |
| **2 — efficiency** | `mean >= floor × threshold` (default 0.75) | `at` (green) — using the declared tolerance. Otherwise `below` (amber) — unused tolerance: over-controlled, or an appetite set too high / estimate understated. A review signal, not an all-clear. |

**Gates 0 and 1 are independent and neither subsumes the other.** A fat-tailed
risk (median ≪ mean) can exceed appetite in expectation while its breach
probability stays modest; a wide-banded risk can sit under appetite in
expectation with a probable breach. Different failures; both red.

Colour is position, probability is tail, and one never decides the other. Green
is bounded **below** by the mean floor ("are you using it?") and **above** by
both the appetite line and the breach probability ("are you about to blow through
it?"). Green therefore requires controlled uncertainty as an emergent property: a
mean at 85% of appetite with bands wide enough to push `p_exceed` past `p_red`
reads red.

Both parameters are configuration (`green_band_floor`, `appetite_red_prob` on
`enterprise.yaml`), not constants — they are decisions and read as such.

> **Retired (v2.5 §1): the straddle branch.** An earlier rule read a band that
> *straddled* appetite as the truest "at appetite" and painted it green. It
> evaluated before the mean check and overrode it, so any risk with a wide enough
> right tail turned green regardless of where its centre sat — the chart drew the
> mean while the colour keyed off the tail. It is gone. A wide band grazing
> appetite from a low mean is amber.

Consequence: the "within appetite" set is mostly amber *possibly
over-controlling* signals, not a green all-clear.

### Capacity vs appetite, read as exceedance

Two enterprise lines (spec §4):

- **Declared appetite** = `appetite_pct_of_revenue × revenue_annual` — a
  revenue-percent line that scales with the company.
- **Capacity** = `capacity_materiality` — the hard audit line the company cannot
  cross by choice.

Named-risk appetites are **authored bottom-up** (v2.2 §D); the enterprise lines
are top-down constraints the rolled-up aggregate must satisfy. **When the
bottom-up aggregate exceeds declared appetite, that is itself the signal**
(`portfolio().over_appetite`). Domains are monitored rollups with **no hard
per-domain ceiling** (a per-domain budget is where a model like this drifts into
arbitrary allocation).

For a **hard line, the tail is the question, not the mean** (v2.2 §E). A band
whose upper bound grazes capacity can still cross it a meaningful fraction of the
time, and that gap between the visual and the probability is the reason to
compute the number. `PortfolioResult` carries `p_over_appetite` and
`p_over_capacity` — the share of simulated trials crossing each line, from the
same portfolio samples (no new path into residual) — and `NamedRiskResidual`
carries `p_over_threshold` for drill-down. The dashboard states **one position
and one probability**: *"Residual $10.8M–$17.5M against a $10M appetite: over.
Roughly a 20% chance of crossing the $15M materiality line this year"* — never
"mean within, upper bound crosses", which are two statements that argue with each
other.

## 4. Emerging, surfaced separately

Emerging scenarios (`lifecycle_state: emerging`) carry deliberately wide, moving
intervals. They are computed but **held out of the appetite-tested aggregate** —
`named_risk_residual` and `portfolio` include managed scenarios only; emerging
items come back through `emerging_items()`, ranked widest-interval-first, each
flagged `would_breach` if its upper bound exceeds its named risk's appetite.

**Amber disambiguation (required, spec §4):** the appetite banding's amber
(`below` = below appetite) and the emerging track's amber (not yet
appetite-tested) are kept structurally distinct — a below-appetite managed risk
is a `NamedRiskResidual(state="below")`; an emerging item is an `EmergingItem`
that never carries a RAG state at all. The dashboard (Day 4) places them in
different columns so they never read as the same thing.

## Control health (derived, diagnostic only)

Per control, a RAG rollup from two inputs — it **never re-enters residual**:

- **Open-issue burden** — findings weighted by severity (critical 4, high 3,
  medium 2, low 1) plus each open accepted exception on the control (a gap,
  weight 2). Burden ≥ 6 → red; ≥ 2 → amber.
- **Evidence coverage/freshness** — the worst status over the control's evidence
  (`missing` > `stale` > `fresh`; `none` if uncovered). Stale or missing evidence
  degrades an otherwise-clean control to amber.

This yields the "provability" signal (spec §5.5): a control can be **green on
findings but amber because its evidence is stale or missing**
(`clean_but_unproven`), and `A.8.5` (secure authentication) is **red from a
finding cluster** (spec §5.4) while `A.8.8` is red from clustered
accepted-vulnerability exceptions.

## KRIs — signals and triggers

A KRI *informs* re-estimation of the factor it points at (residual moves only
because the interval changed, never through an additive KRI term) and *triggers*
emerging-risk changes when it breaches. The engine surfaces KRIs as light signals
on a risk (`kri_signals_for_named_risk`) and the breached set as triggers
(`breached_kris`) — it does not auto-re-estimate (that would rewrite the record);
the seam for live ingestion is the KRI record shape (spec §8).

## Threshold invariants and domain rollups (v2.1 §D1, §D2)

- **Threshold-vs-capacity invariants** (`validation.py`): a named-risk threshold
  above enterprise capacity is a hard **error**; above a quarter of capacity, or
  a threshold sum above 3× the declared appetite, is a **flag** ("the model
  telling on itself"). A managed scenario whose residual band high crosses
  capacity is surfaced by `scenarios_over_capacity()` (engine-side, since it
  needs the residual).
- **Domain RAG counts** (`DomainRollup.rag_counts`, `amber_end_to_end`): a rollup
  of constituent named-risk RAG states — not a per-domain dollar ceiling, so §4
  still holds — making "this domain is amber end to end" a checkable statement.

## Ported views (v2.2 §C)

The legacy v1 engine/report were retired; two capabilities were ported onto the
graph because they drive dashboard views the engine did not already cover
(`graph_views.py`, exposed as `risk-ledger drift` / `risk-ledger renewals`):

- **Drift** — the per-OKR two-ledger read: an OKR's *reported* footprint (the
  exceptions filed on it) versus its *true* footprint once the `diverted_to`
  reallocation from other OKRs is counted. Reuses the engine's per-issue
  contribution samples; the gap is undeclared risk debt.
- **Renewals / can-kicking** — "temporary forever" exceptions renewed past the
  alert count without their justification revisited, plus remediations whose
  target date has already slipped.

## What is next (Day 4)

The dashboard: the brand HTML/CSS shell and the views plus the portfolio
summary — carrying the one-position/one-probability read and the drift wiring —
built on these engine outputs with baked SVG charts. (The view set shipped at seven
and was pruned to five in v3.3; `emerging_items` and `breached_kris` remain engine
outputs even though the horizon view that rendered them was cut.)
