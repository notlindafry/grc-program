# GRC operating model, as data

A git-native model of a full GRC operating model for a regulated, hypergrowth,
fintech-shaped company — represented as data, not a platform. Policy governs
Control; Control mitigates Risk; Issue degrades Control and moves a Risk factor;
Evidence proves Control; Remediation restores it; Risk threatens OKR; Appetite
bounds Risk. Every quantity is a calibrated 90% confidence interval measured
against an **authored** appetite, and the corpus is read as a whole to surface
three things most organizations cannot see:

- **Mis-allocation**: a breached risk and idle, unused tolerance in the *same
  domain, under the same owner* — the budget to cover the breach already exists
  and is merely pointed at the wrong risk, so one person can move it. It asks for
  no new money, which is what makes it the sharpest read in the book — a
  reallocation, not a ratio (view 2). Over-control is its weaker parent: unused
  tolerance says a domain is gold-plated, but not that the fix is already funded
  next door.
- **Drift**: an OKR quietly carrying risk debt reallocated from other goals.
- **Appetite breach**: a risk pushed past its tolerance, often by accumulation
  rather than any single decision — and the aggregate pushed past the enterprise
  line, which is itself the signal.

There is no server and no database. Records are YAML under version control,
changed by pull request, so a risk decision and its approval are reviewable the
way a code change is, and the git history is the audit trail. The relational
structure (Domain → Named risk → Scenario → Issue, plus Controls, Policies,
Evidence, KRIs, Horizon) is **derived at build time** into an in-memory graph.

## Why this exists

The motivating case is a cloud migration under a hard deadline. Each exception
was locally reasonable: accept an unpatched vulnerability, take on some debt,
pull a few engineers off another project, all to hit the date. Read one at a
time, every one was fine. Read together they told a different story: an OKR whose
stated intent was a quality rebuild quietly becoming a lift-and-shift with
accumulated debt, starving other work to do it. No single approval was wrong.
**The aggregate was the signal, and nothing in a standard workflow surfaces it.**

This models the whole operating model around that gap: the quantified risk, the
controls that mitigate it, the evidence that proves them, the appetite that
bounds them, and the OKRs they threaten — so the aggregate reads can be taken.

## How it works

**The model spine — three risk tiers over an issues floor**, organized by where
the risk manifests:

| Tier | Entity | Altitude |
|---|---|---|
| 1 | **Domain** — where risk manifests (7: Resilience, Data integrity, Security, Privacy, Change & delivery, Third-party, Compliance) | board / portfolio |
| 2 | **Named risk** — owned; appetite is set here | executive (VP) |
| 3 | **Scenario** — the quantified loss event the Monte Carlo runs on | practitioner |
| floor | **Issues** — exceptions, findings | operational owners |

Two cross-cutting dimensions apply *across* the domains: **impact** (who bears
the harm) and **AI as a causation vector**. Both are tags on a scenario, and the
portfolio can pivot to either. See **[`docs/schema.md`](docs/schema.md)** for
every entity shape with a populated example, **[`docs/engine.md`](docs/engine.md)**
for the aggregation and banding, and **[`docs/corpus-stories.md`](docs/corpus-stories.md)**
for the designed stories the corpus tells. **[`docs/next-steps.md`](docs/next-steps.md)**
draws the scope line: what a full build would add (live evidence collection,
policy-as-code, live incident mapping, intake/triage, KRI ingestion, tier-aware
dedup) and what is deliberately left out.

**The quant** is a deliberately light, domain-neutral adaptation loosely inspired
by FAIR's frequency-times-magnitude decomposition, generalized so non-adversarial
tech risks (outages, data integrity) sit in the same model as adversarial ones.
It borrows FAIR's shape, not its rigor: the lineage is kept visible, the
adaptation is the point, and the tool does not claim conformance to the standard.
Each scenario is three estimated variables, each a 90% confidence interval:

| Variable | Meaning |
|---|---|
| **Opportunity Frequency (OF)** | how many times a year a condition arises that could produce this loss |
| **Probability of Realization (PoR)** | given that condition, the chance the loss is realized; control failure is folded in, so a preventive-control gap has a clean home |
| **Loss Magnitude (LM)** | loss in dollars if the loss event occurs |

```
Loss Event Frequency (LEF) = OF × PoR
Annualized Loss Exposure (ALE) = LEF × LM
```

**One path into residual.** Only factor-moving issues (`exception` — a risk
acceptance, including a won't-fix accepted vulnerability filed with
`reason: accepted_vulnerability`) change a scenario's residual. Finding
severity, control health, evidence
freshness, and KRIs *inform* the estimate; none adds its own term. Scenario
residuals aggregate up to the named risk, the domain, and the portfolio. A light
Monte Carlo (pure standard library, reproducible) produces every band.

**Appetite is a two-sided target, authored not derived.** Each named risk's
dollar appetite is set by hand from what the company tolerates for that risk —
regulatory constraint, strategic upside, reversibility, concentration — with an
`appetite_rationale` on the record. It is **never** computed from the residual;
the RAG colour is an outcome of that authored line meeting the exposure, decided
by **three gates** (`rag_band`, SPEC v2.6) evaluated in order, where colour is
position and probability is tail — one never determines the other:

- **Gate 0, position → red.** `mean ≥ appetite`: expected loss at or past the
  declared line **is** the breach, full stop. Appetite is a statement about
  expected annual loss, so this is not a probability question and no tail
  argument rescues it.
- **Gate 1, danger → red.** `P(loss > appetite) ≥ 1/3`: a reasonably probable
  breach, whatever the mean. A risk whose average looks comfortable but whose tail
  crosses the line one year in three is still the actionable fact.
- **Gate 2, efficiency.** Among risks under the line and unlikely to breach, a
  mean **using the tolerance you declared** (≥ 75% of appetite) reads **green —
  at appetite**; anything lower reads **amber — below appetite**: unused
  tolerance, over-controlled, or an appetite set too high. A review signal, not
  an all-clear. Not "straddles the line" — a wide band that merely grazes
  appetite from a low mean is amber, not green.

**Gates 0 and 1 are independent; neither subsumes the other.** A fat-tailed risk
can sit past appetite in expectation while its breach probability stays modest
(gate 0 catches it); a wide-banded risk can sit under appetite in expectation yet
breach probably (gate 1 catches it). Different failures, both red, which is why
both gates exist rather than one.

Green therefore requires both good positioning *and* controlled uncertainty: a
mean at 85% with bands wide enough to push the breach probability past a third
reads red. You cannot claim to operate at appetite if you do not know where you
are.

**Exceedance, not eyeballing.** Against a hard line the tail is the question, not
the mean. The portfolio states one position and one probability: *"Residual
$12.6M–$15.1M against a $10M appetite: over. Roughly a 6% chance of crossing the
$15M materiality line this year."*

## Install

```bash
pip install -e .          # the only runtime dependency is PyYAML
```

## Use

```bash
risk-ledger graph                    # load the corpus, validate the derived graph, confirm cardinalities
risk-ledger portfolio                # residual aggregation, appetite/capacity, control health, emerging
risk-ledger drift [OKR]              # per-OKR reported-vs-true footprint (undeclared risk debt)
risk-ledger renewals                 # the can-you-keep-kicking view: temporary-forever + slipped work
risk-ledger dashboard                # render the executive dashboard (the hero artifact) to HTML
risk-ledger grc                      # render the GRC-program tab (landing scorecard) to HTML
```

By default the tool reads the corpus in `./data`. Regenerate the whole
synthetic corpus with `python examples/generate_ecosystem.py`.

The hero artifact is an executive dashboard rendered from this corpus by
`risk-ledger dashboard` (a single self-contained dark HTML page — a "Do this
first" Top-5 action banner, a portfolio summary, a closed set of five views, an
AI coverage lens, and one worked AI example, with charts baked as inline SVG and
no JS framework, SPEC §6/§7). It writes to `docs/dashboard.html`, which the deploy
Action publishes to Vercel:

**▶ Live on Vercel:**
[Engineering Org GRC Profile](https://grc-report.vercel.app/) ·
[GRC program health — WIP](https://grc-report.vercel.app/grc.html)

A GitHub Action ([`.github/workflows/deploy-report.yml`](.github/workflows/deploy-report.yml))
regenerates from the corpus and redeploys on every push to `main`. Each live
page links back to this repo in its footer.

`risk-ledger grc` renders the **GRC tab** (v4.0, work in progress) to
`docs/grc.html` — a page for a GRC Manager measuring the health of the
program itself (coverage, hygiene, SLA throughput, AI governance), not the risk
portfolio. The two pages are presented as **tabs of one view** — a shared tab
bar switches between the Engineering Org GRC Profile and GRC program health. The
GRC page reads additional registers (`regulations.yaml`, `sla_config.yaml`,
`guardrails.yaml`, `agent_inventory.yaml`, `guardrail_events/`) that the eng
build never opens, so
**GRC data cannot move any engineering number** — the isolation guarantee,
enforced by a test that renders the eng dashboard with and without the GRC
corpus loaded and asserts they are identical; guardrail deviations live outside
`data/issues/` and never enter residual.

> ⚠️ **The deploy is public and automatic.** Every push to `main` publishes
> whatever is in `data/` to the live URL — there is no separate "make this
> public" step. The shipped corpus is **synthetic**; do not commit real or
> sensitive risk data unless you intend it to be world-readable. Protect `main`
> (require PR review) so nothing publishes unreviewed. The page is served with
> `noindex` and a `robots.txt` deny to keep it out of search.

## The records

YAML under version control, one coherent corpus. Reference registers are single
files (`enterprise.yaml`, `domains.yaml`, `named_risks.yaml`, `controls.yaml` —
the full ISO 27001:2022 Annex A set of 93 — `policies.yaml`, `evidence.yaml`,
`kris.yaml`, `horizon.yaml`, `okrs.yaml`, `estimators.yaml`); records that
represent an individually reviewable decision get one file each (`scenarios/`,
`issues/`, `remediations/`). The v4.0 GRC tab adds registers the eng build never
reads — `regulations.yaml`, `sla_config.yaml`, `guardrails.yaml`,
`agent_inventory.yaml`, and the `guardrail_events/` directory (guardrail
deviations, kept out of `issues/` so they never enter residual). Every shape is
documented with a populated example in **[`docs/schema.md`](docs/schema.md)**.

## Scope and non-goals

This is a **model of the whole operating model, deliberately not a platform**. It
translates GRC into an engineering leader's language and instruments the aggregate
reads the platforms bury in workflow modules.

- Git-native, no server, no database in the core. The security surface is near
  zero by design (a static, read-only page generated from synthetic YAML — no
  login, no input, no forms, no backend, no queries).
- **Not** a GRC platform: no workflow engine, no intake UI, no ticketing, no live
  pipelines or collectors. Automation ships as *data plus a documented seam* (the
  evidence/KRI record shapes a real collector would later fill; the incident →
  scenario AI mapping runs once offline and is stored as data), never as a live
  feature.
- **Not** a quantification-engine rebuild and not a FAIR-CAM control-efficacy
  model. Calibrated 90% CIs are the unit; a light Monte Carlo only. The FAIR
  lineage is kept visible and conformance is explicitly **not** claimed.

If the demo is ever repointed at real data, the standard auth / RBAC /
rate-limiting / input-validation requirements — intentionally omitted here because
the surface is a static synthetic page — must be revisited before deploying.

## Development

```bash
pip install -e ".[dev]"
pytest
```

> **Note on published figures.** The corpus was recalibrated when appetite moved
> to authored values; any specific figure cited in an earlier post (e.g. a prior
> platform-outage band) no longer matches this corpus. The stories are unchanged;
> the numbers are the current, coherent ones in [`docs/corpus-stories.md`](docs/corpus-stories.md).
