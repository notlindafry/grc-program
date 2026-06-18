# Company Corp Exceptions Risk Report

**Generated 2026-06-18 · Scope: all active exceptions · 49 records, 7 OKRs, 13 mapped risks**

---

## Top line

Across the active exception corpus, the **gcloud-migration** OKR is the dominant source of newly accepted risk and **3 risks now carry residual exposure above appetite**. Fixing the EXC-2026-0170 — Run core services single-region to cut infrastructure cost would clear the largest single share of it.

---

## Drift

Each OKR has two footprints: the risk it accepts on itself, and the risk it pushes onto the OKRs it pulled resources from. The second is invisible on its own ledger.

### gcloud-migration

**gcloud-migration** — objective: a quality rebuild from monolith to microservices. On itself, 16 exceptions accept debt or defer hardening to hit the deadline, adding $18.1M–$71.2M to its own risks. On other OKRs, 19 exceptions name gcloud-migration as where their resources went, adding $30.1M–$62.1M to those OKRs' risks (payments-launch (9), data-platform (6), trust-and-safety (3), and core-platform (1)). Acceptance went from 6 in the first quarter to 28 in the final 8 weeks — accelerating sharply into the deadline. The work traded these key results for the date and pulled 4 other teams' capacity to do it.

**Key results at stake:**
- all services decomposed and hardened by cutover
- maintain 99.9% availability through and after cutover
- zero critical security findings at cutover

| Footprint | Exceptions | Added residual risk |
|---|---|---|
| Internal (on itself) | 16 | $18.1M–$71.2M |
| External (on starved OKRs) | 19 | $30.1M–$62.1M |
| **Combined** | 35 | $54.3M–$119.1M |

**External footprint by starved OKR**

| OKR (filer) | Exceptions | Added residual risk |
|---|---|---|
| payments-launch | 9 | $10.8M–$20.5M |
| data-platform | 6 | $7.2M–$18.2M |
| trust-and-safety | 3 | $1.7M–$5.5M |
| core-platform | 1 | $3.3M–$31.1M |

**Trajectory** (2026-01-12 – 2026-06-14)

| Month | Exceptions filed | Month Over Month Change |
|---|---|---|
| 2026-01 | 1 | — |
| 2026-02 | 2 | +100% |
| 2026-03 | 3 | +50% |
| 2026-04 | 1 | -67% |
| 2026-05 | 19 | +1800% |
| 2026-06 | 9 | -53% |

---

## Appetite breach

Stated tolerance across 13 tracked risks sums to **$179.0M**; the acceptances on the books reveal the organization is carrying **$80.6M–$149.1M** in residual annual loss. 2 risks over and 1 risk straddling appetite.

### RISK-PLATFORM-OUTAGE — OVER appetite

RISK-PLATFORM-OUTAGE carries **$16.4M–$79.0M** in residual annual loss against a **$15.0M** appetite, and the band sits fully above the line. This is a **single-acceptance breach**: EXC-2026-0170 (Run core services single-region to cut infrastructure cost) accounts for 65% of the contributed exposure. One owner, one decision to revisit.

| Exception | What was accepted | Contribution | Over alone? | Owner |
|---|---|---|---|---|
| EXC-2026-0170 | Run core services single-region to cut infrastructure cost | $6.1M–$58.2M | maybe | platform-lead@company.com |
| EXC-2026-0171 | Skip quarterly platform DR test to free the team for migration | $3.3M–$31.1M | maybe | platform-lead@company.com |

### RISK-ACCT-TAKEOVER — OVER appetite

RISK-ACCT-TAKEOVER carries **$8.3M–$16.1M** in residual annual loss against a **$5.0M** appetite, and the band sits fully above the line. This is an **accumulation breach**: no single exception caused it — the top 3 accepted gaps each looked tolerable on its own, and together they breach. There is no individual to send this back to; it is a process signal.

| Exception | What was accepted | Contribution | Over alone? | Owner |
|---|---|---|---|---|
| EXC-2026-0151 | Service-account sprawl on migrated workloads | $1.0M–$7.2M | maybe | iam-lead@company.com |
| EXC-2026-0142 | Skip MFA on internal analytics console to hit migration cutover | $265k–$1.7M | no | platform-lead@company.com |
| EXC-2026-0120 | Allow shared break-glass account on legacy jobs runner | $257k–$1.6M | no | platform-lead@company.com |
| EXC-2026-0124 | Allow legacy API keys on internal data browser | $258k–$1.5M | no | platform-lead@company.com |
| EXC-2026-0127 | Defer MFA on legacy ops console (cutover) | $249k–$1.4M | no | platform-lead@company.com |
| EXC-2026-0122 | Keep password-only auth on legacy build server | $249k–$1.4M | no | platform-lead@company.com |
| EXC-2026-0118 | Relax session timeout on legacy admin portal during cutover | $235k–$1.3M | no | platform-lead@company.com |
| EXC-2026-0125 | Skip MFA on legacy reporting console (cutover) | $218k–$1.3M | no | platform-lead@company.com |
| EXC-2026-0123 | Defer MFA on internal feature-flag console | $214k–$1.2M | no | platform-lead@company.com |
| EXC-2026-0128 | Keep shared admin login on legacy queue manager (cutover) | $207k–$1.2M | no | platform-lead@company.com |
| EXC-2026-0119 | Defer MFA rollout on internal wiki during migration | $188k–$1.1M | no | platform-lead@company.com |
| EXC-2026-0126 | Relax auth on internal scheduler UI (cutover) | $180k–$1.0M | no | platform-lead@company.com |
| EXC-2026-0121 | Skip MFA on internal metrics dashboard for cutover window | $173k–$989k | no | platform-lead@company.com |

### RISK-DATA-EXFIL — STRADDLING appetite

RISK-DATA-EXFIL carries **$3.5M–$13.4M** in residual annual loss against a **$6.0M** appetite, and the band crosses the line, so whether you are over depends on the high end. This is a **single-acceptance breach**: EXC-2026-0133 (DLP disabled on the analytics export path) accounts for 76% of the contributed exposure. One owner, one decision to revisit.

| Exception | What was accepted | Contribution | Over alone? | Owner |
|---|---|---|---|---|
| EXC-2026-0133 | DLP disabled on the analytics export path | $1.2M–$9.7M | maybe | data-platform-lead@company.com |
| EXC-2026-0134 | DLP sampling reduced on warehouse export job | $206k–$1.6M | no | data-platform-lead@company.com |
| EXC-2026-0135 | DLP disabled on ad-hoc BI export connector | $192k–$1.4M | no | data-platform-lead@company.com |

**Within appetite:** RISK-PCI-SCOPE, RISK-PAYMENT-FRAUD, RISK-DATA-QUALITY, RISK-DATA-AVAILABILITY, RISK-ABUSE-ESCALATION, RISK-ABUSE-DETECTION, RISK-MIGRATION-AVAILABILITY, RISK-ENDPOINT-MALWARE, RISK-MIGRATION-DATAINTEGRITY, and RISK-VENDOR-ACCESS.

---

## Persistence

A temporary exception renewed unchanged is the rule in disguise: the acceptance keeps coming back without anyone revisiting whether it still holds.

8 active exceptions have been renewed at least once; **5 have been renewed 3 or more times with the justification never revisited**, carrying **$765k–$2.6M** in residual annual loss. That is 'temporary' becoming permanent.

| Exception | What was accepted | Renewals | Mapped risk | Owner |
|---|---|---|---|---|
| EXC-2026-0310 | Temporary vendor access for mobile analytics SDK | 5 | VENDOR-ACCESS | mobile-lead@company.com |
| EXC-2026-0312 | Allow read-only vendor access to internal dashboards | 4 | VENDOR-ACCESS | mobile-lead@company.com |
| EXC-2026-0314 | Temporary vendor SSH to internal-tools sandbox | 4 | VENDOR-ACCESS | it-lead@company.com |
| EXC-2026-0122 | Keep password-only auth on legacy build server | 3 | ACCT-TAKEOVER | platform-lead@company.com |
| EXC-2026-0313 | Defer EDR upgrade on internal-tools jump host | 3 | ENDPOINT-MALWARE | it-lead@company.com |

---

## Ranked list — what to fix first

Grouped by root cause (the control deviated from), ranked by expected residual contribution. Each row is ready to assign. Only clusters that breach an appetite — or whose upper bound alone would — are listed; clusters that sit within appetite appear in the drift view, not here.

| Rank | Cluster / exception | Expected residual | Breaches | Action to take | Owner | Notes |
|---|---|---|---|---|---|---|
| 1 | EXC-2026-0170 — Run core services single-region to cut infrastructure cost | $6.1M–$58.2M | PLATFORM-OUTAGE | Deploy multi region active active in order to reduce probability of realization no later than 2026-12-01 | platform-lead@company.com | well-formed |
| 2 | EXC-2026-0171 — Skip quarterly platform DR test to free the team for migration | $3.3M–$31.1M | PLATFORM-OUTAGE | Resume quarterly dr tests in order to reduce probability of realization no later than 2026-09-30 | platform-lead@company.com | well-formed |
| 3 | IAM-LEGACY-AUTH-001 (cluster, 12 exceptions) | $5.7M–$9.7M | ACCT-TAKEOVER | Enforce sso via idp in order to reduce probability of realization no later than 2026-09-01 | platform-lead@company.com | 4 of 12 malformed, re-assess first |
| 4 | DLP-EXPORT-001 (cluster, 3 exceptions) | $2.3M–$11.1M | DATA-EXFIL | Re enable dlp with tuned rules in order to reduce loss magnitude no later than 2026-09-01 | data-platform-lead@company.com | well-formed |
| 5 | EXC-2026-0151 — Service-account sprawl on migrated workloads | $1.0M–$7.2M | ACCT-TAKEOVER | Rotate and scope service accounts in order to reduce probability of realization no later than 2026-09-01 | iam-lead@company.com | upper bound alone breaches appetite (tail risk) |

*10 further clusters contribute to risks that remain within appetite and are not ranked here.*

### Sent back, not ranked

A theatrical exception cannot be actioned. These are returned for a real assessment before they can be assigned.

- **Non-plan remediation** (EXC-2026-0125, EXC-2026-0126, EXC-2026-0127, and EXC-2026-0128) — no target date and/or mechanism — returned for a real plan.
- **Reallocation with no destination** (EXC-2026-0140) — reason is resource_reallocation with no diverted_to — returned to state where the resources went.
- **Uncalibrated or stale estimate** (EXC-2026-0149, EXC-2026-0301, and EXC-2026-0302) — estimate not from a calibrated, in-window estimator — returned for re-estimation.

---

## Data confidence

46 of 49 records rest on calibrated, in-window estimates with explicit scope. 3 records rest on uncalibrated, stale, or vaguely-scoped inputs and are excluded from every band until corrected. 8 records are flagged and held out of the rankings until corrected. 

All figures are 90% confidence ranges from a 10,000-iteration light Monte Carlo (lognormal for frequency and magnitude, logit-normal for probabilities), seeded (seed 20260617) for a reproducible audit trail. Contributions are summed as independent marginal estimates — a deliberate light-fidelity simplification, since real effects can interact. Read these as relative magnitudes, not precise valuations.
