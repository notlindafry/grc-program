# Exception Risk Ledger

A git-native tool that treats security exceptions as a **risk process**, not a
compliance one. Every exception is a calibrated estimate of how much it raises
residual risk on a mapped risk, measured against a numeric appetite. Read as a
whole, the corpus of exceptions becomes a measurement instrument for three
things most organizations cannot see:

- **Drift**: an OKR quietly moving away from its stated intent.
- **Appetite breach**: a risk pushed past its stated tolerance, often by
  accumulation rather than any single decision.
- **What to fix first**: funded remediations and unfunded breaching clusters in
  one ranking, ordered by the risk reduction each buys down, with the theatrical
  exceptions sent back instead of actioned.

There is no server and no database. Records are YAML under version control,
changed by pull request, so a risk decision and its approval are reviewable the
way a code change is, and the git history is the audit trail.

## Why this exists

Most organizations run exceptions as a compliance process. A request is filed,
approved, given an expiry, and renewed until someone tires of it. The record
sits in a workflow tool and the corpus is never read as a whole.

The motivating case is a cloud migration under a hard deadline. Each exception
was locally reasonable: accept an unpatched vulnerability, take on some debt,
pull a few engineers off another project, all to hit the date. Read one at a
time, every one was fine. Read together they told a different story: an OKR
whose stated intent was a quality rebuild quietly becoming a lift-and-shift with
accumulated debt, starving other work to do it. No single
approval was wrong. **The aggregate was the signal, and nothing in a standard
exception workflow surfaces it.**

This tool instruments the corpus. The danger of accumulated risk acceptance is
well recognized in the field (e.g. ISC2, Oct 2025: accepted risks compound into
interconnected exposure, and a temporary exception slowly becomes the rule).
What has been missing is any tool that measures it. That is the gap this fills.

## How it works

The model is a deliberately light, domain-neutral adaptation loosely inspired by
FAIR's frequency-times-magnitude decomposition, generalized so non-adversarial
tech risks (outages, data integrity) sit in the same model as adversarial ones
(account takeover, data exfiltration). It borrows FAIR's shape, not its rigor:
the lineage is kept visible, the adaptation is the point, and the tool does not
claim conformance to the standard. Risk is three estimated variables, each a 90%
confidence interval:

| Variable | Meaning |
|---|---|
| **Opportunity Frequency (OF)** | how many times a year a condition arises that could produce this loss: a threat contact, a disruption, a risky deploy (environmental) |
| **Probability of Realization (PoR)** | given that condition, the chance the loss event is actually realized; control failure is deliberately folded in, so a preventive-control gap has a clean home |
| **Loss Magnitude (LM)** | loss in dollars if the loss event occurs |

```
Loss Event Frequency (LEF) = OF × PoR
Annualized Loss Exposure (ALE) = LEF × LM
```

An exception names the **one** variable it moves and supplies the new range. The
tool runs a light Monte Carlo to get the baseline ALE per risk, the marginal
contribution of each exception, and the current residual per risk. Every result
is a band, never a point. It compares each residual band to the risk's numeric
appetite and reports three states: **over**, **straddling**, **within**.

The same residual-contribution math underlies all the outputs: one engine, a few
lenses. See [`docs/methodology.md`](docs/methodology.md) for the distribution and
iteration choices, the breach-classification rules, and the remediation model.

## Install

```bash
pip install -e .          # the only runtime dependency is PyYAML
```

## Use

```bash
risk-ledger validate                 # run the honesty gates; non-zero exit on errors
risk-ledger graph                    # load the GRC-ecosystem model, validate the derived graph, confirm cardinalities
risk-ledger portfolio                # the GRC-ecosystem engine: residual aggregation, appetite/capacity, control health, emerging
risk-ledger report                   # the full narrative report (markdown, to stdout)
risk-ledger report --html            # formatted HTML report, written to report.html and opened in your browser
risk-ledger drift [OKR]              # per-OKR drift lens
risk-ledger appetite [RISK]          # per-risk appetite-breach lens
risk-ledger ranked                   # the ranked action list
risk-ledger renewals                 # persistence: "temporary forever" exceptions renewed unchanged
```

By default the tool reads the corpus in `./data`. A worked example corpus ships
there, and the report it produces is committed at
[`docs/example-report.md`](docs/example-report.md), with a rendered
[`docs/example-report.html`](docs/example-report.html) alongside it. Regenerate
the corpus and both snapshots with `python examples/generate_corpus.py`.

The charts only render in the HTML, and GitHub serves committed `.html` as
source rather than a live page, so the rendered report is also published to
Vercel — open it in a browser, no download needed:

**▶ [Live report](https://grc-report.vercel.app)**

A GitHub Action ([`.github/workflows/deploy-report.yml`](.github/workflows/deploy-report.yml))
regenerates the report from the corpus and redeploys on every push to `main`, so
the live page never drifts from the data.

> ⚠️ **The deploy is public and automatic.** Every push to `main` publishes
> whatever is in `data/` to the live URL above — there is no separate "make this
> public" step. The shipped corpus is synthetic; do **not** commit real or
> sensitive risk data unless you intend it to be world-readable. Protect `main`
> (require PR review) so nothing publishes unreviewed, and prefer Vercel
> Password Protection or your own auth if the report ever carries real data. The
> page is served with `noindex` and a `robots.txt` deny to keep it out of search.

<details>
<summary>One-time Vercel setup</summary>

The Action ships a prebuilt static page, so the Vercel project needs no framework
or build settings.

1. Create a Vercel project — `vercel link` locally, or "Add New… → Project" in the
   dashboard. (Disable Vercel's own Git integration for this repo so it doesn't
   double-deploy alongside the Action.)
2. Add three repository secrets under **Settings → Secrets and variables → Actions**:
   - `VERCEL_TOKEN` — Vercel **Account Settings → Tokens**.
   - `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` — from `.vercel/project.json` after a
     local `vercel link`, or the project's settings.
3. Push to `main` (or run the workflow manually from the Actions tab) to deploy,
   then replace the URL above with the one Vercel assigns.

</details>

```bash
risk-ledger --data data report --out report.md
risk-ledger --as-of 2026-06-18 --seed 20260617 appetite RISK-ACCT-TAKEOVER
```

## GRC ecosystem model (v2, in progress)

The ledger is being extended into a full GRC operating model represented as
data: Tier-1 domains → Tier-2 named risks → Tier-3 scenarios (the quantified
unit) over an issues floor (exceptions, vulns, findings), with the ISO
27001:2022 Annex A control backbone, policies, evidence, KRIs, and an emerging
watch list. YAML stays the system of record; the relational structure is derived
at build time into an in-memory graph, and the existing FAIR-shaped Monte Carlo
is reused unchanged. See **[`docs/schema.md`](docs/schema.md)** for the finalized
entity shapes, one populated example each, and the cardinality confirmation; run
`risk-ledger graph` to load and validate it. The engine that aggregates residual
up the tree (scenario → named risk → domain → portfolio), applies the two-sided
appetite banding, and derives control health is documented in
**[`docs/engine.md`](docs/engine.md)**; run `risk-ledger portfolio` to see it. The
synthetic corpus is seeded backward from the stories the dashboard must tell and
self-calibrates its appetite thresholds at build time — see
**[`docs/corpus-stories.md`](docs/corpus-stories.md)**. This v2 corpus is
decoupled from the frozen legacy v1 corpus, so the legacy exception-ledger
commands and their output above are unchanged.

## The records

Five YAML file types under version control. The first three are the SPEC's;
`okrs.yaml` and `remediations/REM-*.yaml` are additions documented below.

### `risks.yaml`: the light register

One entry per tracked risk, holding the shared baseline and the appetite so they
are not duplicated across exceptions and cannot drift.

```yaml
RISK-ACCT-TAKEOVER:
  title: Account takeover of an internal system via credential compromise
  baseline:
    opportunity_frequency_90ci: [10, 40]
    probability_of_realization_90ci: [0.005, 0.02]   # actor acts AND succeeds (vulnerability folded in)
    loss_magnitude_90ci: [200000, 500000]
  appetite_threshold: 500000                     # residual annual loss this risk must stay under
```

### `exceptions/EXC-*.yaml`: one file per exception

```yaml
id: EXC-2026-0142
title: Skip MFA on internal analytics console to hit migration cutover
owner: platform-lead@company.com       # accountable owner; see "On owner" below
filed_on: 2026-05-06

okr: gcloud-migration                  # links to an OKR so drift can be measured
control: IAM-LEGACY-AUTH-001           # control being deviated from; used for clustering
mapped_risk: RISK-ACCT-TAKEOVER        # MANDATORY. references risks.yaml.

exception_effect:
  moves: probability_of_realization    # exactly one of: opportunity_frequency | probability_of_realization | loss_magnitude
  with_exception_90ci: [0.012, 0.035]  # the new range for the moved variable
  estimated_by: r.chen@company.com     # must resolve to a calibrated estimator
  estimated_on: 2026-04-15

reason: timeline                       # resource_reallocation | technical_constraint | timeline | cost | other
# when reason is resource_reallocation, add reason_detail.diverted_to naming the
# OKR the resources went TO. The exception is filed on the STARVED OKR.
scope:
  type: enumerated                     # enumerated | population
  assets: [analytics-console-prod]     # explicit. "all internal systems" is rejected.
remediation:
  target_date: 2026-09-01              # REQUIRED. absence flags the record as a non-plan.
  mechanism: enforce_sso_via_idp       # REQUIRED.
  reduces: probability_of_realization
status: active                         # active | lapsed | remediated | withdrawn
expires_on: 2026-09-01
renewals:
  count: 0
  justification_changed_last: null     # renewed N times unchanged flags "temporary forever"
```

**On `owner`.** The exception `owner` is the party accountable for the gap this
exception accepts. Accountability here is defined by the remediation lever, not the
blast radius: the owner is whoever holds the authority to close the gap (patch the
vulnerability, re-enable the control, rearchitect the asset), and whose decision it
therefore is to keep it open or to revisit it. If an unpatched vulnerability is
accepted, the accountable owner is the asset or application owner who controls the
patch, not the security organization that answers for overall posture. Second line
owns the appetite this is measured against and the aggregate read across the whole
corpus; it does not own the individual acceptances it exists to measure
independently. One exception, one accountable owner.

The owner is deliberately not the filer (who merely logged the record), not the
`estimated_by` calibrator (who supplied the numbers, not the authority), and not
whoever later executes the remediation. The accountable owner decides; a remediation
owner does. These are usually the same person, and when they differ, the exception
owner is the one who decided to accept.

This is also the unit the views attribute exposure to. When the appetite and
persistence lenses ask whose decisions the carried exposure traces to, the answer is
read from `owner`, so the field must name a specific accountable party, not a queue
or a team alias.

*Other ownership roles are distinct and will be named separately as they are added*
(an OKR's owner, a remediation's owner, the owner of a risk's stated appetite). They
answer different questions and must not be conflated with the exception owner above.

### `estimators.yaml`: the calibration gate

```yaml
r.chen@company.com:
  calibrated: true
  calibrated_on: 2026-03-15            # flagged if missing, or older than the refresh window
```

### `okrs.yaml`: objective and key results per OKR

Not one of the SPEC's three file types. The drift view's headline names the OKR's
*objective* ("a quality microservices rebuild") and displays its *key results* as
the commitments the exception footprint is eroding, and that has to live
somewhere git-native; this minimal register is its home. The optional
`period_end` lets the trajectory analysis measure the run-up to a real deadline
rather than guessing one.

```yaml
gcloud-migration:
  title: gcloud-migration
  objective: a quality rebuild from monolith to microservices
  key_results:
    - all services decomposed and hardened by cutover
    - maintain 99.9% availability through and after cutover
    - zero critical security findings at cutover
  period_end: 2026-06-30
```

### `remediations/REM-*.yaml`: the funded plan

A remediation is a static, version-controlled record of work that buys risk
back down. There is no workflow and no scheduling here: a remediation is filed,
reviewed by pull request, and given a `status`. Only `funded` and `in_progress`
remediations are projected into the post-remediation ("after the plan") figures;
a `proposed` one is carried but not counted, so the projection never credits
work nobody has committed to. Each does exactly one thing:

- **`restore`** returns a control's accepted exceptions to baseline (the gap is
  closed, the cluster's contribution clears). It names `restores_control`.
- **`strengthen`** moves one factor of one mapped risk to an explicit calibrated
  band (a new, better number, not a return to baseline). It names `mapped_risk`,
  the factor it `moves`, the `post_control_90ci` it moves to, and an
  `estimated_by` that passes the same calibration gate as an exception.

```yaml
# restore: close the gap, clear the cluster
id: REM-2026-0001
title: Enforce SSO via the IdP across legacy consoles
type: restore                          # restore | strengthen
status: funded                         # funded | in_progress | proposed
target_date: 2026-09-01
owner: platform-lead@company.com
mechanism: enforce_sso_via_idp
restores_control: IAM-LEGACY-AUTH-001  # the control whose exceptions return to baseline
```

```yaml
# strengthen: move one factor to a new calibrated band
id: REM-2026-0005
title: Implement automated data-residency controls
type: strengthen
status: funded
target_date: 2026-10-01
owner: data-platform-lead@company.com
mechanism: implement_automated_data_residency_controls
mapped_risk: RISK-DATA-RESIDENCY
moves: loss_magnitude                  # the one factor it improves
post_control_90ci: [1000000, 3000000]  # the new 90% CI for that factor
estimated_by: r.chen@company.com       # calibration-gated, like an exception
estimated_on: 2026-06-01
```

Post-remediation composition is first-order: the projection clears or improves
the addressed factors and recomputes, it does not model second-round
interactions. See [`docs/methodology.md`](docs/methodology.md) for how risk
reduction is quantified.

## The honesty gates

Each rule exists because the matching field is where exceptions get gamed. They
come in two tiers:

- **Errors (rejected).** Uncomputable or invariant-violating: an unknown or
  missing `mapped_risk`, `moves` not naming exactly one variable, a missing or
  point-estimate `with_exception_90ci`, a probability range outside `(0,1)`. The
  CLI exits non-zero, so a malformed record cannot be merged silently.
- **Flags (kept, handled specially):**
  - *Trust flags*: the number cannot be believed (uncalibrated or stale
    estimator, vague scope). Excluded from every computed band and surfaced
    separately as untrusted exposure.
  - *Action flags*: the number is fine but the record is not actionable as
    written (no remediation plan, a `resource_reallocation` with no
    `diverted_to`). It still counts in the residual, but is pulled out of the
    ranked list and sent back.

## Scope and non-goals

- Git-native, no server, no database in the core. The security surface is near
  zero by design.
- Not a quantification-engine rebuild and not a FAIR-CAM control-efficacy model.
  Calibrated 90% CIs are the unit; light Monte Carlo only.
- Not a GRC platform. Small, opinionated, scoped to one thing the platforms bury
  in a workflow module.

## Development

```bash
pip install -e ".[dev]"
pytest
```
