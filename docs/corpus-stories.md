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

## Acceptance (v2.5 §6, supersedes v2.3 §F where they overlap)

The RAG rule is now the **two-gate** rule (v2.5 §2): colour is position, probability
is tail. Gate 1 — `P(loss > appetite) ≥ 1/3` reads red, whatever the mean. Gate 2 —
among risks unlikely to breach, `mean ≥ 75% of appetite` reads green, else amber.
The old "a straddle is the truest at-appetite" branch is gone; a wide tail can no
longer paint a low-mean risk green.

| Check | Result |
|---|---|
| No straddle branch; no AT via a band high alone | gone ✓ |
| `rag_band` takes `p_exceed`; `floor` / `p_red` are config | ✓ |
| No AT with `mean/appetite < 0.75` | none (all AT 76–82%) ✓ |
| No AT with `P(exceed) ≥ 0.33` | none (all AT 10–21%) ✓ |
| Green is real: 5–6 AT, each mean 75–95% of appetite | **5 AT** across Security, Data integrity, Change, Third-party ✓ |
| Exactly one domain amber end to end, and it is Privacy; Security mixed | Privacy 5/5 BELOW; Security 1 OVER / 2 AT / 4 BELOW ✓ |
| `P(exceed)` surfaced on every AT/BELOW row ≥ 10% | view 1 ✓ |
| No threshold or rationale changed this pass | `git diff data/named_risks.yaml` empty ✓ |
| Dominance holds; no negative residual | 0 hard errors ✓ |
| P(>capacity) 5–8%, P(>appetite) > 90% | **6%** and **>99%** (v2.8 §1 compressed the tail) ✓ |
| Portfolio well under 1% of revenue, over appetite | mean **$13.8M** = 0.69%, over the $10M line ✓ |

Portfolio residual **$12.6M–$15.1M** (mean $13.8M). One position: **over the $10M
appetite** (the entire range sits above the line). One probability: **a ~6% chance
of crossing the $15M materiality line this year** — a governance moment, not a
crisis. Five risks operate *at* appetite, so the portfolio carries more than the
pre-v2.5 book; v2.8 §1 then compressed the right tail (the mean held at $13.8M while
p95 fell from ~$15.7M to ~$15.1M) to bring the materiality probability back into the
5–8% governance band without scaling exposure uniformly. The RAG spread is
**3 OVER / 5 AT / 14 BELOW**,
judged not fitted (v2.2 §B): a few breaches, green demonstrably achievable across
four domains, a majority over-controlled. Sum of authored thresholds ≈ $36M (3.6×
the declared appetite — the "bottom-up appetite has drifted above the top-down
line" flag fires, which is on-thesis).

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

**Enough green to contrast, and it is real green now (v2.5 §3).** Five named risks
read AT — `NR-ABUSE-ESCALATION` and `NR-ABUSE-DETECTION` (Security),
`NR-DATA-QUALITY` (Data integrity), `NR-MIGRATION-AVAILABILITY` (Change), and
`NR-SUPPLIER-OUTAGE` (Third-party) — each with a residual **mean of 76–82% of its
authored appetite** and a breach probability under a third, so it is green because
it is *operating at appetite*, not because a wide tail grazed the line. Spread
across four domains, green is demonstrably achievable rather than a rigged
impossibility. **Security reads mixed** (1 OVER / 2 AT / 4 BELOW), not a wall of
amber, so Privacy is the conspicuous reveal and not merely the second-most-amber
domain. Those AT risks also keep Data integrity, Change, and Third-party from
reading amber end to end, leaving Privacy the sole standout.

The three OVER risks show both danger paths (v2.5 §2, gate 1). `NR-PLATFORM-OUTAGE`
and `NR-PCI-SCOPE` breach on the **mean** — the bar sits past the appetite tick.
`NR-PROD-COMPROMISE` breaches on the **tail**: its mean sits just *under* appetite
(~96%) yet it reads red because a ~38% chance of crossing the line is the
actionable fact. On view 1 its bar ends left of the tick while its whisker crosses
it — the clearest teaching case for why colour is position and probability is
tail, and one never decides the other.

## Can-kicking inputs (view 5)

**26** remediations carry `target_date`s already in the past (slipped), across a
status spread of 10 funded / 16 in_progress / 14 proposed; six exceptions have
been renewed ≥3× unchanged (`EXC-2026-0102`, `-0105`, `-0160`, `-0162`, `-0164`,
and the DR-test `-0131`).
