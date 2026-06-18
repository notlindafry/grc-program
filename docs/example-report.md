# Company Corp Exceptions Risk Report

**Generated 2026-06-18 · Scope: all active exceptions · 49 records, 7 OKRs, 14 mapped risks**

Every figure in this report is annual loss exposure: the expected loss per year, with event frequency already folded in. None of it is single-loss expectancy — a magnitude is multiplied by how often the loss event occurs before it appears here.

---

## Top line

The **gcloud-migration** OKR is the dominant source of newly accepted risk. **2 risks over appetite** and 1 risk straddling today; the funded plan is projected to clear all but 1 risk (PLATFORM-OUTAGE), whose fix is not funded. This reads the accepted-exception and funded-remediation book, not a complete risk register.

---

## 2026 risk exposure

Entering 2026 the book carried **$21.0M–$38.0M** in residual annual loss exposure (0 over appetite). Mid-year it stands at **$119.4M–$289.6M** (2 over). If the funded plan executes it exits 2026 at **$68.7M–$172.4M** (1 over). The move from entering to exiting is the headline; these bands do not add to a to-the-dollar waterfall.

Two forces move the book: the 2026 acceptances pushed it up (the gcloud-migration OKR alone adds $84.6M–$252.8M); the funded plan pulls it down (4 funded remediations, the largest buying down $17.5M–$139.4M).

The exit figure is a projection conditional on the funded plan executing; RISK-PLATFORM-OUTAGE is projected to remain over, its fix unfunded.

<!--RL-RAW-SVG-->
<svg class="rl-chart" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 218" width="720" height="218"><title>2026 annual loss exposure arc</title><rect x="0" y="0" width="720" height="218" fill="#fff"/><line x1="432.5" y1="32" x2="432.5" y2="172" stroke="#1a1a1a" stroke-width="1.3" stroke-dasharray="5 4"/><text x="432.5" y="22" class="rl-muted" text-anchor="middle">aggregate annual appetite $193M</text><text x="140" y="63" class="rl-label" text-anchor="end">entering 2026</text><text x="194.9" y="46" class="rl-muted" text-anchor="middle">$21–38M</text><rect x="182.5" y="51" width="24.7" height="16" rx="2" fill="#5b7a99"/><text x="597" y="63" class="rl-within" text-anchor="start">0 over appetite</text><text x="140" y="109" class="rl-label" text-anchor="end">mid-year (today)</text><text x="449.2" y="92" class="rl-muted" text-anchor="middle">$119–290M</text><rect x="325.6" y="97" width="247.3" height="16" rx="2" fill="#5b7a99"/><text x="597" y="109" class="rl-over" text-anchor="start">2 over appetite</text><text x="140" y="155" class="rl-label" text-anchor="end">exiting 2026</text><text x="327.2" y="138" class="rl-muted" text-anchor="middle">$69–172M</text><rect x="251.8" y="143" width="150.7" height="16" rx="2" fill="#5b7a99"/><text x="597" y="155" class="rl-straddling" text-anchor="start">1 over appetite</text><line x1="152" y1="178" x2="588" y2="178" stroke="#ccc" stroke-width="1.0"/><line x1="152" y1="178" x2="152" y2="182" stroke="#ccc" stroke-width="1.0"/><text x="152" y="193" class="rl-muted" text-anchor="middle">0</text><line x1="297.3" y1="178" x2="297.3" y2="182" stroke="#ccc" stroke-width="1.0"/><text x="297.3" y="193" class="rl-muted" text-anchor="middle">100</text><line x1="442.7" y1="178" x2="442.7" y2="182" stroke="#ccc" stroke-width="1.0"/><text x="442.7" y="193" class="rl-muted" text-anchor="middle">200</text><line x1="588" y1="178" x2="588" y2="182" stroke="#ccc" stroke-width="1.0"/><text x="588" y="193" class="rl-muted" text-anchor="middle">300</text><text x="370" y="210" class="rl-label" text-anchor="middle">annual loss exposure ($M)</text></svg>
<!--/RL-RAW-SVG-->

---

## Drift

Each OKR has two footprints: the risk it accepts on itself, and the risk it pushes onto the OKRs it pulled resources from. The second is invisible on its own ledger.

### gcloud-migration

**gcloud-migration** — objective: a quality rebuild from monolith to microservices. On itself, 16 exceptions accept debt or defer hardening to hit the deadline, adding $27.3M–$148.8M to its own risks. On other OKRs, 19 exceptions name gcloud-migration as where their resources went, adding $42.6M–$145.2M to those OKRs' risks (payments-launch (9), data-platform (6), trust-and-safety (3), and core-platform (1)). Acceptance went from 6 in the first quarter to 28 in the final 8 weeks — accelerating sharply into the deadline. The work traded these key results for the date and pulled 4 other teams' capacity to do it.

**Key results at stake:**
- all services decomposed and hardened by cutover
- maintain 99.9% availability through and after cutover
- zero critical security findings at cutover

| Footprint | Exceptions | Added residual risk |
|---|---|---|
| Internal (on itself) | 16 | $27.3M–$148.8M |
| External (on starved OKRs) | 19 | $42.6M–$145.2M |
| **Combined** | 35 | $84.6M–$252.8M |

**External footprint by starved OKR**

| OKR (filer) | Exceptions | Added residual risk |
|---|---|---|
| payments-launch | 9 | $10.8M–$20.5M |
| data-platform | 6 | $7.2M–$18.2M |
| trust-and-safety | 3 | $1.7M–$5.5M |
| core-platform | 1 | $13.8M–$114.3M |

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

Stated tolerance across 14 tracked risks sums to **$193.0M**; the acceptances on the books reveal the organization is carrying **$119.4M–$289.6M** in residual annual loss exposure. 2 risks over and 1 risk straddling appetite.

Of the 3 risks over or straddling appetite today, 1 risk (RISK-PLATFORM-OUTAGE) remains over after the funded plan executes. Projections below are conditional on that plan.

<!--RL-RAW-SVG-->
<svg class="rl-chart" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 320" width="600" height="320"><title>Per-risk appetite ranges, current vs after plan</title><rect x="0" y="0" width="600" height="320" fill="#fff"/><text x="0" y="23" class="rl-label" text-anchor="start">RISK-PLATFORM-OUTAGE <tspan class="rl-over">over → still over</tspan></text><text x="80" y="58.5" class="rl-muted" text-anchor="end">current</text><rect x="184.2" y="47" width="331" height="15" rx="2" fill="#b00020"/><text x="80" y="82.5" class="rl-muted" text-anchor="end">after plan</text><rect x="121.3" y="71" width="200.3" height="15" rx="2" fill="#b00020" fill-opacity="0.12" stroke="#b00020" stroke-width="1.5"/><line x1="117.9" y1="44" x2="117.9" y2="89" stroke="#1a1a1a" stroke-width="1.3" stroke-dasharray="5 4"/><text x="117.9" y="42" class="rl-muted" text-anchor="start">annual appetite $15M</text><text x="0" y="129" class="rl-label" text-anchor="start">RISK-ACCT-TAKEOVER <tspan class="rl-within">over → within</tspan></text><text x="80" y="164.5" class="rl-muted" text-anchor="end">current</text><rect x="313.2" y="153" width="150.1" height="15" rx="2" fill="#b00020"/><text x="80" y="188.5" class="rl-muted" text-anchor="end">after plan</text><rect x="107.4" y="177" width="62.4" height="15" rx="2" fill="#0a7d33" fill-opacity="0.12" stroke="#0a7d33" stroke-width="1.5"/><line x1="254" y1="150" x2="254" y2="195" stroke="#1a1a1a" stroke-width="1.3" stroke-dasharray="5 4"/><text x="254" y="148" class="rl-muted" text-anchor="middle">annual appetite $5M</text><text x="0" y="235" class="rl-label" text-anchor="start">RISK-DATA-EXFIL <tspan class="rl-within">straddling → within</tspan></text><text x="80" y="270.5" class="rl-muted" text-anchor="end">current</text><rect x="204.1" y="259" width="329.7" height="15" rx="2" fill="#b06a00"/><text x="80" y="294.5" class="rl-muted" text-anchor="end">after plan</text><rect x="103" y="283" width="126.2" height="15" rx="2" fill="#0a7d33" fill-opacity="0.12" stroke="#0a7d33" stroke-width="1.5"/><line x1="287.2" y1="256" x2="287.2" y2="301" stroke="#1a1a1a" stroke-width="1.3" stroke-dasharray="5 4"/><text x="287.2" y="254" class="rl-muted" text-anchor="middle">annual appetite $6M</text></svg>
<!--/RL-RAW-SVG-->

### RISK-PLATFORM-OUTAGE — OVER appetite

RISK-PLATFORM-OUTAGE carries **$48.3M–$214.5M** in residual annual loss exposure against a **$15.0M** appetite, and the band sits fully above the line. This is a **single-acceptance breach**: EXC-2026-0170 (Run core services single-region to cut infrastructure cost) accounts for 55% of the contributed annual loss exposure. One owner, one decision to revisit.

| Exception | What was accepted | Contribution | Over alone? | Owner |
|---|---|---|---|---|
| EXC-2026-0170 | Run core services single-region to cut infrastructure cost | $17.5M–$139.4M | yes | platform-lead@company.com |
| EXC-2026-0171 | Skip quarterly platform DR test to free the team for migration | $13.8M–$114.3M | yes | platform-lead@company.com |

**After the funded plan** (Deploy multi-region active-active for core services): projected to **remain over** appetite, at **$16.7M–$117.3M** residual. Conditional on the funded plan executing.

### RISK-ACCT-TAKEOVER — OVER appetite

RISK-ACCT-TAKEOVER carries **$6.8M–$11.3M** in residual annual loss exposure against a **$5.0M** appetite, and the band sits fully above the line. This is an **accumulation breach**: no single exception caused it — the top 3 accepted gaps each looked tolerable on its own, and together they breach. There is no individual to send this back to; it is a process signal.

| Exception | What was accepted | Contribution | Over alone? | Owner |
|---|---|---|---|---|
| EXC-2026-0142 | Skip MFA on internal analytics console to hit migration cutover | $265k–$1.7M | no | platform-lead@company.com |
| EXC-2026-0120 | Allow shared break-glass account on legacy jobs runner | $257k–$1.6M | no | platform-lead@company.com |
| EXC-2026-0124 | Allow legacy API keys on internal data browser | $258k–$1.5M | no | platform-lead@company.com |
| EXC-2026-0127 | Defer MFA on legacy ops console (cutover) | $249k–$1.4M | no | platform-lead@company.com |
| EXC-2026-0122 | Keep password-only auth on legacy build server | $249k–$1.4M | no | platform-lead@company.com |
| EXC-2026-0118 | Relax session timeout on legacy admin portal during cutover | $235k–$1.3M | no | platform-lead@company.com |
| EXC-2026-0125 | Skip MFA on legacy reporting console (cutover) | $218k–$1.3M | no | platform-lead@company.com |
| EXC-2026-0123 | Defer MFA on internal feature-flag console | $214k–$1.2M | no | platform-lead@company.com |
| EXC-2026-0128 | Keep shared admin login on legacy queue manager (cutover) | $207k–$1.2M | no | platform-lead@company.com |
| EXC-2026-0151 | Service-account sprawl on migrated workloads | $198k–$1.1M | no | iam-lead@company.com |
| EXC-2026-0119 | Defer MFA rollout on internal wiki during migration | $188k–$1.1M | no | platform-lead@company.com |
| EXC-2026-0126 | Relax auth on internal scheduler UI (cutover) | $180k–$1.0M | no | platform-lead@company.com |
| EXC-2026-0121 | Skip MFA on internal metrics dashboard for cutover window | $173k–$989k | no | platform-lead@company.com |

**After the funded plan** (Enforce SSO via the IdP across legacy consoles): projected **within** appetite, at **$584k–$2.5M** residual. Conditional on the funded plan executing.

### RISK-DATA-EXFIL — STRADDLING appetite

RISK-DATA-EXFIL carries **$3.5M–$13.4M** in residual annual loss exposure against a **$6.0M** appetite, and the band crosses the line, so whether you are over depends on the high end. This is a **single-acceptance breach**: EXC-2026-0133 (DLP disabled on the analytics export path) accounts for 76% of the contributed annual loss exposure. One owner, one decision to revisit.

| Exception | What was accepted | Contribution | Over alone? | Owner |
|---|---|---|---|---|
| EXC-2026-0133 | DLP disabled on the analytics export path | $1.2M–$9.7M | maybe | data-platform-lead@company.com |
| EXC-2026-0134 | DLP sampling reduced on warehouse export job | $206k–$1.6M | no | data-platform-lead@company.com |
| EXC-2026-0135 | DLP disabled on ad-hoc BI export connector | $192k–$1.4M | no | data-platform-lead@company.com |

**After the funded plan** (Re-enable DLP with tuned rules on export paths): projected **within** appetite, at **$452k–$4.3M** residual. Conditional on the funded plan executing.

**Within appetite:** RISK-PCI-SCOPE, RISK-PAYMENT-FRAUD, RISK-DATA-QUALITY, RISK-DATA-RESIDENCY, RISK-DATA-AVAILABILITY, RISK-ABUSE-ESCALATION, RISK-ABUSE-DETECTION, RISK-MIGRATION-AVAILABILITY, RISK-ENDPOINT-MALWARE, RISK-MIGRATION-DATAINTEGRITY, and RISK-VENDOR-ACCESS.

---

## Persistence

A temporary exception renewed unchanged is the rule in disguise: the acceptance keeps coming back without anyone revisiting whether it still holds.

8 active exceptions have been renewed at least once; **5 have been renewed 3 or more times with the justification never revisited**, carrying **$765k–$2.6M** in residual annual loss exposure. That is 'temporary' becoming permanent.

| Exception | What was accepted | Renewals | Mapped risk | Owner |
|---|---|---|---|---|
| EXC-2026-0310 | Temporary vendor access for mobile analytics SDK | 5 | VENDOR-ACCESS | mobile-lead@company.com |
| EXC-2026-0312 | Allow read-only vendor access to internal dashboards | 4 | VENDOR-ACCESS | mobile-lead@company.com |
| EXC-2026-0314 | Temporary vendor SSH to internal-tools sandbox | 4 | VENDOR-ACCESS | it-lead@company.com |
| EXC-2026-0122 | Keep password-only auth on legacy build server | 3 | ACCT-TAKEOVER | platform-lead@company.com |
| EXC-2026-0313 | Defer EDR upgrade on internal-tools jump host | 3 | ENDPOINT-MALWARE | it-lead@company.com |

---

## What to fix first

This ranks the work that moves quantified risk, by the residual it buys down, whether the lever is clearing an accepted exception or executing a funded remediation. A risk with no exception and no funded plan does not appear; a risk over appetite with no acceptance behind it is a control-sufficiency problem this view surfaces but does not remediate by clearing an exception.

| Rank | Item | Risk reduction | Breaches | Action to take | Owner |
|---|---|---|---|---|---|
| 1 | REM-2026-0003 — Deploy multi-region active-active for core services | $17.5M–$139.4M | PLATFORM-OUTAGE | Deploy multi region active active in order to reduce probability of realization no later than 2026-12-01 | platform-lead@company.com |
| 2 | EXC-2026-0171 — Skip quarterly platform DR test to free the team for migration | $13.8M–$114.3M | PLATFORM-OUTAGE | Resume quarterly dr tests in order to reduce probability of realization no later than 2026-09-30 | platform-lead@company.com |
| 3 | REM-2026-0001 — Enforce SSO via the IdP across legacy consoles | $5.7M–$9.7M | ACCT-TAKEOVER | Enforce sso via idp in order to reduce probability of realization no later than 2026-09-01 | platform-lead@company.com |
| 4 | REM-2026-0005 — Implement automated data-residency controls | $3.4M–$8.5M | — | Implement automated data residency controls in order to reduce loss magnitude no later than 2026-10-01 | data-platform-lead@company.com |
| 5 | REM-2026-0002 — Re-enable DLP with tuned rules on export paths | $2.3M–$11.1M | DATA-EXFIL | Re enable dlp with tuned rules in order to reduce loss magnitude no later than 2026-09-01 | data-platform-lead@company.com |
| 6 | EXC-2026-0151 — Service-account sprawl on migrated workloads | $198k–$1.1M | ACCT-TAKEOVER | Rotate and scope service accounts in order to reduce probability of realization no later than 2026-09-01 | iam-lead@company.com |

### Sent back, not ranked

A theatrical exception cannot be actioned. These are returned for a real assessment before they can be assigned.

- **Non-plan remediation** (EXC-2026-0125, EXC-2026-0126, EXC-2026-0127, and EXC-2026-0128) — no target date and/or mechanism — returned for a real plan.
- **Reallocation with no destination** (EXC-2026-0140) — reason is resource_reallocation with no diverted_to — returned to state where the resources went.
- **Uncalibrated or stale estimate** (EXC-2026-0149, EXC-2026-0301, and EXC-2026-0302) — estimate not from a calibrated, in-window estimator — returned for re-estimation.

---

## Data confidence

46 of 49 records rest on calibrated, in-window estimates with explicit scope. 3 records rest on uncalibrated, stale, or vaguely-scoped inputs and are excluded from every band until corrected. 8 records are flagged and held out of the rankings until corrected. 

All figures are 90% confidence ranges from a 10,000-iteration light Monte Carlo (lognormal for frequency and magnitude, logit-normal for probabilities), seeded (seed 20260617) for a reproducible audit trail. Contributions are summed as independent marginal estimates — a deliberate light-fidelity simplification, since real effects can interact. Read these as relative magnitudes, not precise valuations.
