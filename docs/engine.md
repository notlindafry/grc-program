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

Only **factor-moving** issues change residual: an `exception` or a `vuln` moves
exactly one scenario factor (OF, PoR, or LM) and its marginal contribution is
added under common random numbers, exactly as in the legacy engine. A `finding`
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

Appetite is a target, not a ceiling. `rag_band(residual, threshold, green_floor)`
returns one of three states, applied to the **managed, calibrated set only**:

| State | Token | Meaning |
|---|---|---|
| `over` | `--status-over` (red) | the whole band sits above appetite — a breach |
| `at` | `--status-at` (green) | the band **straddles** the line (the truest "at appetite"), or sits in the top quarter of tolerance. The only green condition. |
| `below` | `--status-below` (amber) | unused tolerance below the green band — over-controlled, or an appetite set too high / estimate understated. A review signal, not an all-clear. |

The green band's floor defaults to **0.75** (a residual between ~75% and 100% of
appetite reads green), configurable via `green_band_floor` on `enterprise.yaml`.
Consequence: the "within appetite" set is mostly amber *possibly over-controlling*
signals, not a green all-clear.

### Capacity vs appetite

Two enterprise lines (spec §4):

- **Declared appetite** = `appetite_pct_of_revenue × revenue_annual` — a
  revenue-percent line that scales with the company.
- **Capacity** = `capacity_materiality` — the hard audit line the company cannot
  cross by choice.

Named-risk thresholds are bottom-up; the enterprise lines are top-down
constraints the rolled-up aggregate must satisfy. **When the bottom-up aggregate
exceeds declared appetite, that is itself the signal** (`portfolio().over_appetite`)
— it forces remediation or an explicit, board-signed appetite increase. Domains
are monitored rollups with **no hard per-domain ceiling** (a per-domain budget is
where a model like this drifts into arbitrary allocation).

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
  medium 2, low 1) plus each open accepted exception/vuln on the control (a gap,
  weight 2). Burden ≥ 6 → red; ≥ 2 → amber.
- **Evidence coverage/freshness** — the worst status over the control's evidence
  (`missing` > `stale` > `fresh`; `none` if uncovered). Stale or missing evidence
  degrades an otherwise-clean control to amber.

This yields the "provability" signal (spec §5.5): a control can be **green on
findings but amber because its evidence is stale or missing**
(`clean_but_unproven`), and `A.8.5` (secure authentication) is **red from a
finding cluster** (spec §5.4) while `A.8.8` is red from clustered accepted vulns.

## KRIs — signals and triggers

A KRI *informs* re-estimation of the factor it points at (residual moves only
because the interval changed, never through an additive KRI term) and *triggers*
emerging-risk changes when it breaches. The engine surfaces KRIs as light signals
on a risk (`kri_signals_for_named_risk`) and the breached set as triggers
(`breached_kris`) — it does not auto-re-estimate (that would rewrite the record);
the seam for live ingestion is the KRI record shape (spec §8).

## Day-3 additions (spec v2.1)

- **Threshold-vs-capacity invariants** (`validation.py`): a named-risk threshold
  above enterprise capacity is a hard **error**; above a quarter of capacity, or
  a threshold sum above 3× the declared appetite, is a **flag** ("the model
  telling on itself"). A managed scenario whose residual band high crosses
  capacity is surfaced by `scenarios_over_capacity()` (engine-side, since it
  needs the residual).
- **Domain RAG counts** (`DomainRollup.rag_counts`, `amber_end_to_end`): a rollup
  of constituent named-risk RAG states — not a per-domain dollar ceiling, so §4
  still holds — making "this domain is amber end to end" a checkable statement.
- **Self-calibrated corpus:** named-risk thresholds are computed at build time
  from each risk's Monte-Carlo residual to land the designed RAG spread (3 OVER /
  6 AT / 10 BELOW), and exception effects are rescaled to plausible multipliers
  (max 3.2×). See [`docs/corpus-stories.md`](corpus-stories.md).

## What is next (Day 4)

The dashboard: the brand HTML/CSS shell and the six views plus the portfolio
summary, built on these engine outputs with baked SVG charts.
