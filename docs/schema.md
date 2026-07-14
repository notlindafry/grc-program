# GRC ecosystem — entity schema (Day 1)

The system of record is git-native YAML under `data/`. The relational structure
is **derived at build time** into an in-memory graph (`risk_ledger/graph.py`),
never persisted back. This document is the Day-1 deliverable from the build
spec: the finalized shape of every entity (spec §2), one populated example each,
and confirmation that the model loads, validates, and satisfies the spec §3
cardinalities.

Reproduce everything below with:

```bash
python examples/generate_corpus.py     # regenerate the whole corpus (legacy + v2)
risk-ledger --as-of 2026-06-18 graph   # load, validate, and print the cardinality confirmation
```

All data is synthetic (spec §11).

---

## The model spine

Control is the connective tissue. Three risk tiers sit over an issues floor,
organized by **where the risk manifests** (spec §1):

```
Tier 1  Domain        where the risk manifests     board / portfolio altitude   7
Tier 2  Named risk    owned; appetite is set here   executive (VP) altitude      20
Tier 3  Scenario      the quantified loss event     practitioner altitude        22
------------------------- risk / issue boundary -------------------------
        Issues        exceptions, vulns, findings   operational owners           57
```

Two cross-cutting dimensions apply *across* the domains rather than nesting as
tiers: **impact** (who bears the harm) and **AI as a causation vector**. Both
are tags on a scenario, and the dashboard can pivot the portfolio to either.

**One path into residual (spec §4).** Only factor-moving issues — `exception`
and `vuln` — change residual. `finding` severity, control health, evidence
freshness, and KRIs *inform the estimate*; none adds its own term.

---

## Cardinalities (spec §3, locked)

| Relationship | Cardinality | Enforced as |
|---|---|---|
| named risk → domain | many-to-one (tree) | `NR.domain` must resolve (error) |
| scenario → named risk | many-to-one (tree) | `Scenario.named_risk` must resolve (error) |
| issue → scenario | many-to-many; **first is primary** for rollup | ≥1 scenario must resolve (error) |
| issue → control | many-to-many | `control` may be a scalar or a list |
| control → named risk | many-to-many | 0 mapped → "why do we do this?" (flag) |
| control → policy | many-to-one (governing policy) | missing/unknown policy (flag) |
| evidence → control | many-to-many | unknown control (flag) |
| KRI → scenario / named risk | many-to-many (informs) | unknown target (flag) |
| remediation → scenario / issue | many-to-many | `addresses_scenarios` / `addresses_issues` |
| named risk → OKR | many-to-many (threatens) | `threatens_okrs`; starvation from `diverted_to` |

### Cardinality confirmation (shipped corpus, `risk-ledger graph`)

```
Entities: 7 domains · 21 named risks · 23 scenarios · 36 issues
          (exception=28, vuln=3, finding=5) · 93 controls · 17 policies
          · 14 evidence · 12 KRIs · 4 horizon · 40 remediations · 16 OKRs

named_risk → domain (tree):    21/21 resolve to a parent
scenario   → named_risk (tree): 23/23 resolve to a parent
control    → policy (tree):     93/93 resolve to a parent
issue      → scenario (m2m):    36/36 issues mapped
control    → named_risk (m2m):  90/93 controls mapped   (3 deliberate orphans)

orphan_scenarios: 0 · issues_without_scenario: 0 · unmapped_controls: 3
```

No hard errors. Six flags, all intended: three controls deliberately left
unmapped so the "why do we do this?" signal is a rare, meaningful flag; two trust
flags (1 uncalibrated + 1 stale estimator); and one large-threshold
justification flag (a named risk whose appetite exceeds a quarter of enterprise
capacity, spec v2.1 §D1).

> **Day-3 note.** The v2 corpus is now **self-contained and decoupled** from the
> legacy v1 corpus (`risks.yaml`, `exceptions/`), which stays frozen so the v1
> engine and its tests are untouched. v2 issues live under `issues/` (no legacy
> bridge) and v2 remediations under `graph_remediations/`. Named-risk thresholds
> are **calibrated at build time** from each risk's Monte-Carlo residual to land
> the designed RAG spread — see [`docs/corpus-stories.md`](corpus-stories.md).

---

## File layout (spec §2)

Records that represent an individually reviewable decision get one file each;
registers of reference data are single files.

```
data/
  enterprise.yaml      named_risks.yaml    controls.yaml     kris.yaml
  domains.yaml         policies.yaml       evidence.yaml     horizon.yaml
  estimators.yaml      okrs.yaml                             config.yaml
  scenarios/SCN-*.yaml               # Tier 3, one file each
  issues/{EXC,VULN,FND}-*.yaml       # v2 issues (self-contained), one file each
  graph_remediations/REM-*.yaml      # v2 remediations with m2m links, one file each
  # --- frozen legacy v1 corpus, read only by the v1 engine ---
  risks.yaml   exceptions/EXC-*.yaml   remediations/REM-*.yaml
```

The v2 graph loader (`load_graph`) reads only the v2 corpus: `issues/` is
self-contained (no bridge to the legacy `exceptions/`), and remediations come
from `graph_remediations/`. The legacy `load_corpus` / v1 engine path and its
frozen corpus are untouched, so the v2 effects could be recalibrated in Day 3
without disturbing the v1 tests.

---

## One populated example per entity

### `enterprise.yaml` — the appetite anchor (§2.1)

Two dollar figures. `capacity_materiality` is the hard audit line; the declared
appetite is derived (`appetite_pct_of_revenue × revenue_annual = $10M`) and set
beneath it.

```yaml
revenue_annual: 2000000000
capacity_materiality: 15000000
appetite_pct_of_revenue: 0.005      # -> $10M declared appetite
green_band_floor: 0.75              # top quarter of tolerance reads green (§4)
```

### `domains.yaml` — Tier 1 (§2.2)

The seven manifestation domains: Resilience, Data integrity, Security, Privacy,
Change & delivery, Third-party, Compliance. The `appetite_statement` is
board-facing narrative **only**, never tested against a number.

```yaml
TR-PRIVACY:
  title: Privacy
  description: "misused regulated/personal data: residency, retention, consent, subprocessor governance"
  appetite_statement: "regulated-data misuse held near zero; this is a licence-to-operate risk"
  appetite_signed_off_by: dpo@company.com
  appetite_last_reviewed: 2026-05-01
```

### `named_risks.yaml` — Tier 2, the appetite-bearing risk (§2.3)

Many-to-one to a domain. Carries the accountable owner, the bottom-up per-risk
dollar appetite, and the OKRs it threatens (m2m).

```yaml
NR-PROD-COMPROMISE:
  title: Compromise of production systems via credential or access failure
  domain: TR-SECURITY
  owner: security-eng-lead@company.com
  appetite_threshold: 5000000
  threatens_okrs: [gcloud-migration]
```

### `scenarios/SCN-*.yaml` — Tier 3, the quantified unit (§2.4)

The baseline OF/PoR/LM (which used to live on `risks.yaml`) lives here — the
scenario is what the Monte Carlo runs on. `impact` and `vectors` are the
cross-cutting pivots; `lifecycle_state` is `managed | emerging`. `legacy_risk`
bridges the migrated exceptions; `incident` carries the offline AI
incident→scenario mapping (§8), stored as data.

```yaml
id: SCN-2026-0019
title: Second admin-console takeover path via unrotated service accounts
named_risk: NR-PROD-COMPROMISE
baseline:
  opportunity_frequency_90ci: [8, 30]
  probability_of_realization_90ci: [0.006, 0.02]
  loss_magnitude_90ci: [1500000, 4000000]
impact: [financial, individual_harm]
vectors: [adversarial]
lifecycle_state: managed
trajectory: stable
incident:                              # the offline AI mapping seam (§8), as data
  ticket_id: INC-2026-0442
  suggested_domain: TR-SECURITY
  suggested_named_risk: NR-PROD-COMPROMISE
  suggested_factor: probability_of_realization
  suggested_band: at appetite
  mapped_by: offline-ai-incident-mapper
  mapped_on: 2026-06-10
```

An **emerging** scenario looks the same but carries a deliberately wide,
rising-trajectory interval and the `ai` vector (spec §4):

```yaml
id: SCN-2026-0031
title: Confidently-wrong automated decisioning at scale on a single model provider
named_risk: NR-MODEL-SUPPLY
baseline:
  opportunity_frequency_90ci: [5, 60]
  probability_of_realization_90ci: [0.02, 0.30]
  loss_magnitude_90ci: [500000, 12000000]
impact: [financial, individual_harm, public_market_harm]
vectors: [ai, third_party]
lifecycle_state: emerging
trajectory: rising
```

### `issues/` — the floor, generalized with a `type` discriminator (§2.5)

Common fields: `id`, `title`, `owner`, `filed_on`, `status`, `mapped_scenarios`
(first is primary), `control` (scalar or list). Only `exception` and `vuln` move
a factor and enter the residual bands.

**`type: exception`** — the unchanged legacy schema (migrated from
`exceptions/`, still names a single `mapped_risk`):

```yaml
id: EXC-2026-0142
title: Skip MFA on internal analytics console to hit migration cutover
owner: platform-lead@company.com
filed_on: 2026-01-12
okr: gcloud-migration
control: IAM-LEGACY-AUTH-001
mapped_risk: RISK-ACCT-TAKEOVER        # bridged to SCN-2026-0001 via legacy_risk
exception_effect:
  moves: probability_of_realization
  with_exception_90ci: [0.012, 0.035]
  estimated_by: r.chen@company.com
  estimated_on: 2026-04-15
# ... reason, scope, remediation, renewals (schema intact)
```

**`type: vuln`** — an out-of-SLA accepted vulnerability; folds into the
scenario's PoR via a top-level `moves` + `with_acceptance_90ci`:

```yaml
id: VULN-2026-0001
type: vuln
title: Accepted out-of-SLA RCE on a migrated jobs runner
owner: platform-lead@company.com
filed_on: 2026-05-18
status: active
mapped_scenarios: [SCN-2026-0001]
control: [A.8.8]
moves: probability_of_realization
with_acceptance_90ci: [0.02, 0.06]
estimated_by: r.chen@company.com
estimated_on: 2026-05-18
asset: legacy-jobs-runner
expires_on: 2026-08-15
```

**`type: finding`** — audit / incident-PMAI / self-identified; carries a bounded
`severity` that informs control health and the narrative but is **never
simulated**:

```yaml
id: FND-2026-0001
type: finding
title: "Audit: legacy consoles permit password-only authentication"
owner: security-eng-lead@company.com
filed_on: 2026-04-30
status: open
source: audit                          # audit | incident-PMAI | self-identified
severity: high                         # low | medium | high | critical
mapped_scenarios: [SCN-2026-0001]
control: [A.8.5]
```

### `controls.yaml` — the ISO 27001:2022 Annex A backbone (§2.6)

All **93** controls across the four themes (Organizational 37, People 8,
Physical 14, Technological 34), keyed by Annex A reference. Each names its
governing policy (many-to-one) and the named risks it mitigates (m2m). Health is
**derived**, not stored.

```yaml
"A.8.5":
  title: Secure authentication
  theme: Technological
  policy: POL-ACCESS-CONTROL
  mapped_named_risks: [NR-PROD-COMPROMISE]
```

### `policies.yaml` — the governance layer (§2.7)

The coverage read is "every control traces up to a governing policy."

```yaml
POL-ACCESS-CONTROL:
  title: Access Control Policy
  owner: ciso-office@company.com
  last_reviewed: 2026-02-01
  link: https://policies.example.com/access-control
```

### `evidence.yaml` — proof a control operates (§2.8, data only)

No collector is built. `status` (fresh | stale | missing) is **derived** from
`cadence` + `last_collected`. This record is stale (a quarterly control last
collected in November):

```yaml
EV-DR-0001:
  supports_controls: [A.5.30]
  source: dr-test-report
  collection_method: manual            # descriptive only; no collector
  cadence: quarterly
  last_collected: 2025-11-01           # -> status: stale as of 2026-06-18
```

### `kris.yaml` — key risk indicators (§2.9, thin)

A KRI *informs* re-estimation of a factor (never an additive term) and triggers
emerging-risk changes. `status` (ok | amber | breached) is **derived** from
`current_value` vs `threshold`; `direction: under` means low readings breach.

```yaml
KRI-MODEL-CONCENTRATION:
  title: Share of critical paths dependent on a single model provider
  informs: [SCN-2026-0031]
  current_value: 0.62
  threshold: 0.50
  trend: rising
  direction: over                      # over -> breach when value >= threshold
```

### `horizon.yaml` — the emerging watch list (§2.10)

Mechanistic-test fence: an item earns a slot **only** if it names both a
candidate domain and a watched KRI. Validation rejects an item missing either.

```yaml
HZN-AGENT-AUTONOMY:
  title: Autonomous agents taking unsafe action in production
  candidate_domain: TR-CHANGE
  watched_kri: KRI-AGENTIC-WORKFLOWS
  trajectory: rising
  note: "agentic workflows moving into prod ahead of guardrails"
```

### `remediations/REM-*.yaml` — extended (§2.11)

Existing `restore` / `strengthen` types kept. Linkage generalized to
many-to-many via `addresses_scenarios` / `addresses_issues`, and the remediation
sponsor (`owner`) is now distinct from the ticket assignee (`operational_owner`).

```yaml
id: REM-2026-0001
title: Enforce SSO via the IdP across legacy consoles
type: restore
status: funded
target_date: 2026-09-01
owner: platform-lead@company.com
operational_owner: iam-oncall@company.com
mechanism: enforce_sso_via_idp
restores_control: IAM-LEGACY-AUTH-001
addresses_scenarios: [SCN-2026-0001, SCN-2026-0019]
addresses_issues: [VULN-2026-0001]
```

### `okrs.yaml` — extended (§2.12)

Unchanged shape (objective, key_results, period_end). The risk→OKR link is
derived from the named risk's `threatens_okrs`; goal-starvation is read from the
existing exception `reason: resource_reallocation` + `reason_detail.diverted_to`.

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

---

## The Day-1 validation invariants (`validate_graph`)

Errors reject; flags keep the record but surface a diagnostic.

- **Error** — enterprise anchor present with positive figures; named risk names
  a known domain and a positive appetite; scenario names a known named risk and
  a well-formed baseline CI per factor; issue `type` is valid; issue maps to ≥1
  known scenario; a factor-moving issue's moved factor + accepted band are valid;
  a finding's severity is one of low/medium/high/critical; a horizon item names
  **both** a candidate domain and a watched KRI.
- **Flag** — a control mapping to no named risk ("why do we do this?"); a control
  with no/unknown governing policy; evidence/KRI/horizon pointing at an unknown
  target; declared appetite above capacity; a finding with an unknown source.

Trust handling (uncalibrated or stale estimator, vague scope) is inherited from
the exceptions gates and applies to factor-moving issues the same way.

---

## The engine and corpus

The engine that aggregates these entities up the tree, applies the two-sided
appetite banding, and derives control health is documented in
[`docs/engine.md`](engine.md); the designed synthetic corpus and the ten stories
it tells are in [`docs/corpus-stories.md`](corpus-stories.md).
