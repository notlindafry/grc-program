# The designed corpus stories

The synthetic corpus is seeded **backward from the stories the dashboard must
tell** (build spec §5, as revised by v2.1 §E and v2.2 §E/§F). Each story is
identifiable by the IDs listed, so views wire to known data and every claim is
checkable against real output. Reproduce with:

```bash
python examples/generate_ecosystem.py               # regenerate the corpus
risk-ledger --as-of 2026-06-18 portfolio            # the numbers below
risk-ledger --as-of 2026-06-18 graph                # cardinalities + invariants
risk-ledger --as-of 2026-06-18 drift gcloud-migration
risk-ledger --as-of 2026-06-18 renewals
```

All data is synthetic (spec §11).

## Appetite is authored, exposure is tuned

The pivotal correction (v2.2 §D): **appetite is a declared tolerance, authored by
hand** as round numbers in `data/named_risks.yaml`, each with an
`appetite_rationale`. Nothing derives a threshold from a residual. The RAG colour
of each risk is therefore an **outcome** of that authored line meeting tuned
exposure — never a target the threshold was fitted to. The only tuning lever is
the exposure side (scenario baselines and exception effects), because that is
what the business generates; moving appetite to make a risk read a colour would
engineer the conclusion the whole artifact argues against.

The spread below is a *judged outcome*, not a pass/fail gate (v2.2 §B).

## Acceptance (v2.3 §F, supersedes v2.2 §I where they overlap)

| Check | Result |
|---|---|
| No negative residual anywhere | none; the dominance gate holds ✓ |
| Dominance holds for all factor-moving issues | 0 hard errors ✓ |
| The no-op flag fires on nothing | ✓ |
| Exactly one domain amber end to end, and it is Privacy; Security mixed | Privacy 5/5 BELOW; Security 1 OVER / 2 AT / 4 BELOW ✓ |
| Green achievable: ~5–7 AT in more than one domain | **5 AT** across Security, Data integrity, Change, Third-party ✓ |
| P(>capacity) 5–8%, P(>appetite) > 90% | **7.7%** and **97.2%** ✓ |
| No threshold, rationale, or enterprise figure changed this pass | `git diff data/named_risks.yaml data/enterprise.yaml` empty ✓ |
| v2.1 §D1 invariants pass; ten stories still ID-traceable | ✓ |
| Portfolio well under 1% of revenue, over appetite | mean **$12.5M** = 0.62%, over the $10M line ✓ |

Portfolio residual **$10.3M–$15.6M** (mean $12.5M). One position: **over the $10M
appetite** (P > appetite 97%). One probability: **a ~8% chance of crossing the
$15M materiality line this year** — a governance moment, not a crisis. The RAG
spread is **3 OVER / 5 AT / 14 BELOW**, judged not fitted (v2.2 §B): a few
breaches, green demonstrably achievable across four domains, a majority
over-controlled. Sum of authored thresholds ≈ $37M (3.7× the declared appetite —
the "bottom-up appetite has drifted above the top-down line" flag fires, which is
on-thesis).

**Appetite was never the lever.** Every fix in this pass is a story-shaping change
made on the *exposure* side only — scenario baselines and exception effects.
Thresholds, the enterprise appetite, and the capacity line are authored positions
and were not touched (v2.3 §B, checked by the empty diff above). The
semantic **dominance invariant** — an exception weakens a control, so it can only
make the moved factor worse — is now a hard gate in `validation.py`, with a
non-negative-residual backstop in the engine and a no-op flag for effects that
add nothing.

## The ten stories

**1. A named risk OVER appetite from a single large scenario.**
`NR-PLATFORM-OUTAGE` (OVER $2.5M) — dominated by one severe acceptance,
`EXC-2026-0130` (run core services single-region) on `SCN-2026-0013`.

**2. A named risk OVER appetite from accumulation.**
`NR-PROD-COMPROMISE` (OVER $1.5M) — nine small legacy-auth exceptions
(`EXC-2026-0101`…`EXC-2026-0109`) across `SCN-2026-0001`/`SCN-2026-0019`; no one
exception breaches alone, together they clear the line. The drift thesis.

**3. At least two orphan risks** (OVER, no funded remediation).
`NR-PLATFORM-OUTAGE` (no remediation at all) and `NR-PCI-SCOPE` (only a
*proposed* segmentation fix, `REM-2026-0112` — proposed ≠ funded).

**4. A control with poor health from clustered findings.**
`A.8.5` (Secure authentication) → **RED**: `FND-2026-0001`/`0002` (high) +
`FND-2026-0003` (medium). `A.8.8` RED from three accepted vulns.

**5. A control clean on findings but amber on stale/missing evidence.**
`A.8.32` (Change management) → **AMBER**, no findings, evidence missing
(`EV-CHANGE-0001`). Same provability signal on `A.5.34`, `A.8.13` (stale).

**6. An OKR visibly threatened by a top named risk.**
`gcloud-migration` threatened by `NR-PROD-COMPROMISE` (OVER); `payments-launch`
by `NR-PCI-SCOPE` (OVER, orphan). Read from each named risk's `threatens_okrs`.

**7. A `diverted_to` starvation chain.**
`EXC-2026-0150`…`EXC-2026-0154` (+`EXC-2026-0131`) filed on the *starved* OKRs
(`payments-launch`, `trust-and-safety`, `data-platform`, `core-platform`), each
`diverted_to: gcloud-migration`. `risk-ledger drift gcloud-migration` shows the
reported footprint (~$2.6M) versus the true footprint (~$4.1M) — ~$1.5M of
undeclared risk debt the migration's own ledger hides.

**8. One incident → scenario mapping from the offline AI step.**
`SCN-2026-0019` carries an `incident` block (ticket `INC-2026-0442`),
`mapped_by: offline-ai-incident-mapper` — stored as data (spec §8).

**9. The standout amber — now Privacy (v2.2 §F).**
`TR-PRIVACY` reads **amber end to end**: all five named risks
(`NR-DATA-RESIDENCY`, `NR-SUBPROCESSOR-GOV`, `NR-DATA-RETENTION`,
`NR-CONSENT-MGMT`, `NR-PII-MINIMIZATION`) read BELOW, with `NR-CONSENT-MGMT`
dramatically so (residual mean at ~8% of its authored $750k appetite). Privacy is
regulated — so over-control is the canonical failure — and engineering-adjacent
through residency/retention/subprocessor governance, yet a VP reliably files it
as "legal's". Amber end to end there says: *you are gold-plating the domain you
never think about while your platform burns.* Data integrity stays BELOW but is
no longer the hero. Surfaced via the domain `rag_counts` / `amber_end_to_end`.

**10. Emerging risks + horizon + KRI breaches.**
Three emerging scenarios with wide, rising, `ai`-vector intervals
(`SCN-2026-0031/0032/0033`), held out of the appetite math. Four horizon items
(`HZN-*`); ten KRIs breached, feeding the horizon view.

**Enough green to contrast (v2.3 §C, §D).** Five named risks read AT (green) —
`NR-DATA-QUALITY`, `NR-MIGRATION-AVAILABILITY`, `NR-SUPPLIER-OUTAGE`,
`NR-DATA-EXFIL`, and `NR-ABUSE-ESCALATION` — spread across four domains, so green
is demonstrably achievable rather than a rigged impossibility. **Security reads
mixed** (1 OVER / 2 AT / 4 BELOW), not a wall of amber, so Privacy is the
conspicuous reveal and not merely the second-most-amber domain. Those AT risks
also keep Data integrity, Change, and Third-party from reading amber end to end,
leaving Privacy the sole standout.

## Can-kicking inputs (view 5)

**26** remediations carry `target_date`s already in the past (slipped), across a
status spread of 10 funded / 16 in_progress / 14 proposed; six exceptions have
been renewed ≥3× unchanged (`EXC-2026-0102`, `-0105`, `-0160`, `-0162`, `-0164`,
and the DR-test `-0131`).
