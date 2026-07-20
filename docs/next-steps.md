# Next steps

*Tell, not build (build spec §9).* This document is the deliberate scope line.
Everything below is **not built** in this demonstration; it is described so the
shape of the full operating model is legible without pretending the machines are
running. The demo's governing principle (§1.4) is **automation as data plus a
documented seam**: each capability ships as the data structure it would produce,
populated synthetically, plus a marked extension point in the code. The seams
already in the tree are the anchors these next steps attach to — see the
`SEAM` docstrings in `risk_ledger/models.py` (evidence, KRI, intake) and
`examples/generate_ecosystem.py` (`map_incident_to_scenario`).

The ordering below is roughly the order in which the value compounds, not a
sprint plan.

## 1. Automated evidence collection

The GRC-engineering cornerstone. Today an `evidence` record (`SPEC §2.8`) carries
`source`, `collection_method`, `cadence`, and `last_collected`, and its
`fresh | stale | missing` status is derived from cadence against the reference
date. That status already drives the dashboard's *provability* signal: a control
can be clean on findings yet read amber because its evidence is stale or missing.

The next step is a collector that populates `last_collected` (and a pointer to the
raw artifact) on each cadence tick, from the system that actually holds the proof —
CI attestations, ticket exports, access-review snapshots, cloud-config queries. The
model does not change; only the input becomes live. Evidence stays out of the quant
(it informs control health, never a residual term) to keep the single quantitative
path — see next-step 5 for the version that deliberately relaxes that.

## 2. Policy-as-code

Controls trace up to a governing policy today as a text reference. Policy-as-code
makes the control's requirement **machine-readable**, embedded in the policy: the
policy states the testable assertion (e.g. "MFA enforced on all human access to
production"), and the control's health can then be evaluated against a live check
rather than a periodic human attestation. This is the bridge between a control
*claiming* to operate and a control *demonstrably* operating, and it is what makes
next-step 1's collected evidence self-describing rather than a dated file.

## 3. Live incident / issue auto-mapping

The offline AI incident-mapper (`map_incident_to_scenario`, `SPEC §8`) runs once
and stores its output as data; the dashboard's worked AI example shows one real
mapping. The next step repoints its input at a **native incident/issue queue**
(PagerDuty, Jira, ServiceNow) and calls the model per new ticket: raw report →
suggested domain, named risk, scenario, the one factor it moves, and a band. The
return shape and the `mapped_by` / `mapped_on` provenance are unchanged, so the
loader and dashboard read it as-is. The mapping stays **advisory** — it proposes a
move to an existing factor, never adds a term, and never writes without human
confirmation.

## 4. Dynamic intake and triage workflow

Every issue is hand-authored YAML today; `IssueRecord` marks where the intake seam
attaches. The next step puts a workflow in front of that record: raw intake →
suggested taxonomy (type, mapped scenario, moved factor, band) → a **draft**
`IssueRecord` a human confirms before it lands. The confirmed output is exactly the
current shape, so the quant and the dashboard are unchanged; only the authoring path
changes. This is where next-step 3 (incident mapping) and next-step 7 (dedup) plug
in as the smart parts of the intake pipe.

## 5. Second-order remediation composition and evidence-informed uncertainty

Two quant extensions held out on purpose to keep **one quantitative path** in the
demo:

- **Second-order remediation composition.** Model how remediations *interact* —
  a segmentation project that shrinks the blast radius of several scenarios at
  once, or two fixes whose benefit is not additive — rather than treating each
  remediation's effect independently.
- **Evidence-informed control uncertainty.** The version where **stale evidence
  widens a residual band**: an unproven control contributes more modelled
  uncertainty than a freshly-attested one. This deliberately breaks the current
  clean separation (evidence informs health, never the number), so it is called
  out as a distinct modelling decision, not a silent addition.

## 6. KRI live ingestion, alerting, and trend monitoring

A `kri` record (`SPEC §2.9`) is the seam; its `ok | amber | breached` status is
derived from `current_value` against a threshold, and a breach informs
re-estimation of an existing factor and can trigger emerging-risk changes (never an
additive term). The next step connects a **live metric source** (Prometheus, a
metrics warehouse) to populate `current_value` on each refresh, adds **threshold
alerting** and **trend monitoring**, and — further out — **automated KRI-to-factor
mapping** so a new metric proposes which factor it should inform. On the dashboard a
KRI stays a light signal on a risk and a feed into the emerging-risk track (the engine
still computes it; the standalone horizon view was cut in the v3.3 prune), not its own
monitoring product.

## 7. Deduplication checks (tier-aware)

Parked with intake automation (next-step 4), and reusing the same API muscle as the
incident mapper: a similarity match (embeddings or an LLM pass) asking whether a
proposed risk or issue **already exists** before a record is created. The important
part is that it must be **tier-aware**, enforcing the risk/issue/asset line the model
already draws:

- **Risks** are duplicates when they describe the **same scenario** (semantic match →
  merge).
- **Issues** need more care, because near-identical is often legitimate. The same CVE
  across fifty assets is *fifty real issues*; the same finding logged by two auditors
  is *one double-entry*. So issue dedup must separate **same-issue-entered-twice**
  (merge) from **same-class-many-instances** (keep).

Shipping the naive "these look alike, merge them" version would collapse exactly the
distinction the taxonomy exists to hold. The tier-aware version enforces it at
runtime.

---

## Explicitly out of scope (and why)

This artifact is a **model of the operating model**, not a platform — a closed set of
five dashboard views plus a portfolio summary and the Top-5 banner, rendered from
synthetic git-native YAML. There is deliberately **no workflow engine, no live
collectors, and no database**; the view set is closed and each view earns its place by
mapping to a question a VP actually asks (`SPEC v2.7 §8`, pruned seven→five in v3.3 —
Horizon cut, Falling-through-the-cracks folded into view 1). The security posture follows from that shape: a static,
read-only, public HTML page with no login, no user input, and no backend has the same
near-zero surface as the repo it extends, so the standard auth / RBAC / rate-limiting /
input-sanitization requirements are **not applicable and intentionally omitted**
(`SPEC §11`). The relevant controls here are: synthetic data only, `noindex` + `robots`
deny, and protected `main`. **If this is ever repointed at real risk data, revisit that
note before deploying** — put auth or Vercel Password Protection in front of the page
first.
