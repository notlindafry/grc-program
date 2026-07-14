# The designed corpus stories (Day 3)

The synthetic corpus is seeded **backward from the stories the dashboard must
tell** (build spec §5, as revised by spec v2.1 §E). Each story below is
identifiable by the IDs listed, so Day-4 views wire to known data and every claim
is checkable against real output. Reproduce with:

```bash
python examples/generate_corpus.py                 # regenerate (self-calibrates thresholds)
risk-ledger --as-of 2026-06-18 portfolio           # the numbers below
risk-ledger --as-of 2026-06-18 graph               # cardinalities + invariants
```

All data is synthetic (spec §11). Thresholds are **calibrated at build time**
from each named risk's Monte-Carlo residual to land the designed RAG spread, so
the stories survive regeneration.

## Calibration result (spec v2.1 §F acceptance checks)

| Check | Target | Actual |
|---|---|---|
| Portfolio residual (managed) | over $10M appetite, under $15M capacity | mean **$12.2M** (band $9.1M–$16.6M); over appetite ✓, under capacity ✓ |
| Portfolio as % of $2B revenue | well under 1% | **0.61%** ✓ |
| No named-risk threshold > $15M | 0 | **0** ✓ (calibration clamps to capacity) |
| No BELOW risk with band high > $15M | 0 | **0** ✓ (the B2 embarrassment is gone) |
| RAG spread across named risks | ~2-3 / 5-7 / 10-12 | **3 OVER / 6 AT / 10 BELOW** ✓ |
| Exactly one amber-end-to-end domain | 1 | **1** (Data integrity) ✓ |
| No scenario residual/baseline multiplier > ~5x | — | max **3.2x** ✓ |
| remediations ≥ 40 / okrs ≥ 15 | — | **40 / 16** ✓ |

Sum of named-risk thresholds ≈ $25M (2.5× the declared appetite — normal
bottom-up drift, under the 3× "telling on itself" flag). No hard validation
errors; six intended flags (3 orphan controls, 1 stale + 1 uncalibrated
estimator, 1 large-threshold justification).

## The ten stories

**1. A named risk OVER appetite from a single large scenario.**
`NR-PLATFORM-OUTAGE` (OVER) — its residual is dominated by one severe acceptance,
`EXC-2026-0130` (run core services single-region, a ~3× PoR move on
`SCN-2026-0013`). Domain: Resilience.

**2. A named risk OVER appetite from accumulation.**
`NR-PROD-COMPROMISE` (OVER) — no single exception breaches alone; nine small
legacy-auth exceptions (`EXC-2026-0101`…`EXC-2026-0109`, each a modest 1.3–1.7×
PoR move) spread across `SCN-2026-0001` and `SCN-2026-0019` sum over appetite.
The drift thesis.

**3. At least two orphan risks** (OVER, no funded remediation addressing them).
`NR-PLATFORM-OUTAGE` and `NR-PCI-SCOPE`. (PCI-SCOPE has only a *proposed*
segmentation remediation, `REM-2026-0112` — proposed ≠ funded, so it stays an
orphan; PROD-COMPROMISE is OVER but has funded work, so it is not an orphan.)

**4. A control with poor health from clustered findings.**
`A.8.5` (Secure authentication) → **RED**: `FND-2026-0001`, `FND-2026-0002`
(both high) + `FND-2026-0003` (medium). Also `A.8.8` RED from three accepted
vulns (`VULN-2026-0001..0003`).

**5. A control clean on findings but amber on stale/missing evidence.**
`A.8.32` (Change management) → **AMBER**, no findings, evidence missing
(`EV-CHANGE-0001`, `last_collected: null`). Same provability signal on `A.5.34`
and `A.8.13` (stale evidence). The `clean_but_unproven` flag on the engine.

**6. An OKR visibly threatened by a top named risk.**
`gcloud-migration` is threatened by `NR-PROD-COMPROMISE` (OVER) and
`NR-MIGRATION-AVAILABILITY`; `payments-launch` by `NR-PCI-SCOPE` (OVER, orphan).
Read from each named risk's `threatens_okrs`.

**7. A `diverted_to` starvation chain.**
`EXC-2026-0150`…`EXC-2026-0154` (and `EXC-2026-0131`) are filed on the *starved*
OKRs (`payments-launch`, `trust-and-safety`, `data-platform`, `core-platform`)
with `reason: resource_reallocation` and `reason_detail.diverted_to:
gcloud-migration` — the launch that drained them.

**8. One incident → scenario mapping from the offline AI step.**
`SCN-2026-0019` carries an `incident` block (ticket `INC-2026-0442`) with the
suggested domain/named-risk/factor/band, `mapped_by: offline-ai-incident-mapper`
— stored as data so the dashboard renders it as a single worked example (spec §8).

**9. The standout amber (the headline).**
`TR-DATA-INTEGRITY` reads **amber end to end** — both its named risks,
`NR-DATA-QUALITY` and `NR-PIPELINE-INTEGRITY`, read BELOW. `NR-PIPELINE-INTEGRITY`
is the standout, residual mean at ~15% of its threshold. It is the domain with
the *smallest* dollar exposure in the portfolio, so it looks healthy — and that
is the point: amber here means over-controlled / opportunity cost, not safe.
Surfaced via the domain `rag_counts` and `amber_end_to_end`.

**10. Emerging risks + horizon + KRI breaches.**
Three emerging scenarios with wide, rising intervals and the `ai` vector:
`SCN-2026-0031` (single-model concentration), `SCN-2026-0032` (agent autonomy),
`SCN-2026-0033` (detection drift) — held out of the appetite math. Four horizon
items (`HZN-*`), each naming a candidate domain and a watched KRI. Ten KRIs
breached, feeding the horizon view.

**Enough green to contrast.** Six named risks read AT (green) — including
`NR-DATA-EXFIL`, `NR-PAYMENT-FRAUD`, `NR-DATA-RESIDENCY` — so the standout amber
and the red breaches are not the only colours on the board.

## Can-kicking inputs (spec §6 view 5)

Chronic deferral is real, not just open work: **26** remediations carry
`target_date`s already in the past as of 2026-06-18 (slipped), across a status
spread of 10 funded / 16 in_progress / 14 proposed; and six exceptions have been
renewed ≥3 times unchanged (`EXC-2026-0102`, `-0105`, `-0131`, `-0160`, `-0162`,
`-0164`).
