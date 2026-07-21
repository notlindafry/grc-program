"""The GRC tab — landing scorecard and program-health shell (v4.0 Spec 1 §1.D–§1.F).

Reader: a **GRC Manager** (P.1). This page measures the health of the GRC
program itself — coverage, hygiene, throughput, and the governance of AI — not
the risk portfolio. The residual number is the eng tab's and does not lead here.

Rendering decisions, per spec:

* **Separate page** (``docs/grc.html``) with a nav link to the eng dashboard.
  A separate page keeps the eng render byte-identical (P.4); true in-page
  tabbing needs the eng render refactored into a fragment and is deferred.
  DECISION FLAGGED FOR REVIEW: the spec asks for a link "to/from" the eng
  dashboard, but adding the return link to ``dashboard.html`` would break the
  byte-identical gate, so the link is one-way (GRC → eng) until the in-page
  tabbing spec lands.
* **Design system**: the ``:root`` tokens are imported from the eng dashboard
  verbatim — no raw hex in components. RAG per P.9: conventional for
  coverage/hygiene/SLA; two-sided for control right-sizing, where an
  over-engineered control takes ``--status-below`` (amber) and the word
  "over-controlled", never green. Every status marker carries its word.
* **WCAG contrast** (§1.F): verified for the status trio against ``--bg`` and
  ``--surface`` — status-over 7.11/6.04, status-at 8.38/7.12, status-below
  7.94/6.75, status-below-tint 10.05/8.54; all clear the 4.5:1 AA normal-text
  bar, so the trio is safe at the 10–12px table-label size this tab is dense
  with. This closes the standing contrast item.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .dashboard import _ROOT, _esc, money
from .grc import GRCEngine, load_grc_graph

# Component CSS on top of the shared :root tokens (no raw hex here — §1.F).
_CSS = _ROOT + """
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); border-top:3px solid var(--accent);
  font-family:var(--font-body); font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased; }
h1,h2,h3,h4,.col-num,.strip-num { font-family:var(--font-display); font-weight:600; letter-spacing:-0.01em; }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.wrap { max-width:var(--maxw); margin:0 auto; padding:40px 24px 80px; }
header .eyebrow { color:var(--accent); font-size:10.5px; font-weight:600; letter-spacing:0.07em; text-transform:uppercase; }
header h1 { font-size:30px; margin:6px 0 4px; color:var(--text-strong); }
header .meta { color:var(--text-muted); font-size:13.5px; }
.navrow { margin-top:10px; font-size:13px; }
.wip { margin:18px 0 0; border:1px dashed var(--status-below); border-radius:var(--radius);
  background:color-mix(in srgb, var(--status-below), transparent 92%); padding:12px 16px;
  font-size:13px; color:var(--text); }
.wip b { color:var(--status-below-tint); letter-spacing:0.04em; }
.wip .iso { display:block; margin-top:6px; color:var(--text-muted); font-size:12.5px; }
.wip-strong { border-style:solid; }
.cols { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:26px 0 0; }
.col { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px 18px; }
.col h3 { font-size:13px; margin:0 0 10px; color:var(--text-strong); text-transform:uppercase; letter-spacing:0.05em; }
.col-num { font-size:26px; color:var(--text-strong); line-height:1.15; }
.col-den { color:var(--text-muted); font-size:11.5px; margin-top:2px; }
.col-row { border-top:1px solid var(--border); margin-top:10px; padding-top:10px; font-size:12.5px; }
.col-k { color:var(--text-muted); font-size:10.5px; text-transform:uppercase; letter-spacing:0.06em; }
.col-v { margin-top:2px; }
.sowhat { margin-top:10px; font-size:11.5px; color:var(--accent); border:1px solid var(--border);
  border-radius:var(--radius-sm); padding:2px 8px; display:inline-block; }
.subtile { margin-top:12px; border:1px dashed var(--status-below); border-radius:var(--radius-sm);
  padding:8px 10px; font-size:12px; }
.subtile .col-k { color:var(--status-below-tint); }
.strip { margin:14px 0 0; background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:14px 18px; display:flex; gap:18px; flex-wrap:wrap; align-items:baseline; }
.strip-num { font-size:22px; color:var(--text-strong); }
.strip .part { font-size:12px; color:var(--text-muted); }
.note { margin:14px 0 0; color:var(--text-muted); font-size:12.5px; max-width:820px; }
.grid { display:grid; gap:20px; margin-top:26px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:24px 26px; }
.card h2 { font-size:17px; margin:0 0 4px; color:var(--text-strong); }
.card .sub { color:var(--text-muted); font-size:13px; margin:0 0 14px; }
.card h4 { font-size:13.5px; margin:16px 0 8px; color:var(--text-strong); }
table.tbl { width:100%; border-collapse:collapse; font-size:13px; }
.tbl th { text-align:left; color:var(--text-muted); font-weight:500; font-size:11px; text-transform:uppercase;
  letter-spacing:0.04em; padding:6px 10px; border-bottom:1px solid var(--border); }
.tbl td { padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; }
.tbl tr:last-child td { border-bottom:none; }
.tbl .nm { color:var(--text-strong); }
.tbl .drv { color:var(--text-muted); }
.tbl .num { text-align:right; font-family:var(--font-display); white-space:nowrap; }
.st { font-weight:600; font-size:12px; }
.st-over { color:var(--status-over); }
.st-at { color:var(--status-at); }
.st-below { color:var(--status-below-tint); }
.dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; vertical-align:baseline; }
.callout { border-left:3px solid var(--accent); background:var(--bg); padding:10px 14px; margin:14px 0 0;
  border-radius:var(--radius-sm); color:var(--text); font-size:13px; line-height:1.5; max-width:820px; }
.callout.warn { border-left-color:var(--status-below); }
.lede { color:var(--text); font-size:13.5px; margin:0 0 14px; max-width:820px; }
footer { margin-top:40px; color:var(--text-faint); font-size:12.5px; max-width:820px; }
@media (max-width:840px) { .cols { grid-template-columns:repeat(2,1fr); } }
"""

# The three program goals a figure can serve (§1.E "so what" tags).
_GOALS = {
    "risk": "responsible risk-taking",
    "speed": "engineering speed",
    "informed": "informed decisions",
}


def _word_over(text: str) -> str:
    return f'<span class="st st-over"><span class="dot" style="background:var(--status-over)"></span>{_esc(text)}</span>'


def _word_at(text: str) -> str:
    return f'<span class="st st-at"><span class="dot" style="background:var(--status-at)"></span>{_esc(text)}</span>'


def _word_below(text: str) -> str:
    return f'<span class="st st-below"><span class="dot" style="background:var(--status-below)"></span>{_esc(text)}</span>'


def _sla_word(met: int, measured: int) -> str:
    """A conventional-RAG SLA word (P.9): all met -> green; most met -> amber
    (word 'slipping'); under three-quarters -> red (word 'behind')."""
    if measured and met == measured:
        return _word_at("on SLA")
    if measured and met / measured >= 0.75:
        return _word_below("slipping")
    return _word_over("behind")


def _fmt_date(d) -> str:
    return d.isoformat() if d else "—"


# ---------------------------------------------------------------------------
# Landing scorecard (§1.E): four columns, small multiples, no composite.
# ---------------------------------------------------------------------------


def _scorecard(e: GRCEngine) -> str:
    pc = e.policy_currency()
    ac = e.agent_coverage()
    rc = e.requirement_coverage()
    rh = e.risk_hygiene()
    unscored = e.unscored_risks()
    rem = e.remediation_sla()
    ev = e.evidence_freshness()
    no_policy, no_risk = e.unmapped_controls()
    plans = e.findings_without_plan()
    sources = e.finding_sources()
    dev_sla = e.deviation_sla()
    dev_overdue = [s for s in dev_sla if s.met is False and s.dev.is_open]
    n_ev = len(e.graph.evidence)
    n_findings = sum(sources.values())
    scored = len(e.graph.named_risks) - len(unscored)

    worst_pol = pc.overdue[0] if pc.overdue else None
    worst_rem = rem.overdue[0] if rem.overdue else None
    stale_ev = ev["stale"] + ev["missing"]

    gov = (
        '<div class="col"><h3>Governance</h3>'
        f'<div class="col-num">{len(rc.satisfied)}/{rc.total}</div>'
        '<div class="col-den">external requirements (regulations.yaml) satisfied by at least one live control</div>'
        '<div class="col-row"><div class="col-k">Worst-aging hygiene</div><div class="col-v">'
        + (f'{_esc(worst_pol.policy_id)} review <b>{worst_pol.days_overdue}d overdue</b>' if worst_pol else "no overdue policy reviews")
        + '</div></div>'
        f'<div class="col-row"><div class="col-k">SLA</div><div class="col-v">{_sla_word(pc.current, pc.total)}'
        f' <span class="drv">policy reviews on cadence: {pc.current}/{pc.total}</span></div></div>'
        # AI governance rides in the Governance column (§1.E), strongest WIP (P.7).
        '<div class="subtile"><div class="col-k">AI governance · WIP</div>'
        f'<div class="col-v">guardrail coverage <b>{len(ac.covered)}/{len(ac.detected)}</b> detected agents'
        f' · disposition SLA: <b>{len(dev_overdue)}</b> overdue</div></div>'
        f'<div><span class="sowhat">{_GOALS["informed"]}</span></div>'
        '</div>')

    risk = (
        '<div class="col"><h3>Risk</h3>'
        f'<div class="col-num">{scored}/{len(e.graph.named_risks)}</div>'
        '<div class="col-den">named risks (named_risks.yaml) scored by at least one scenario</div>'
        '<div class="col-row"><div class="col-k">Worst-aging hygiene</div><div class="col-v">'
        + (f'{_esc(worst_rem.id)} target <b>{(e.config.as_of - worst_rem.target_date).days}d past</b>' if worst_rem else "no overdue remediations")
        + '</div></div>'
        f'<div class="col-row"><div class="col-k">SLA</div><div class="col-v">'
        f'{_sla_word(rem.total_live - len(rem.overdue), rem.total_live)}'
        f' <span class="drv">remediations on target: {rem.total_live - len(rem.overdue)}/{rem.total_live}</span></div></div>'
        f'<div class="col-row"><div class="col-k">Hygiene pass</div><div class="col-v">{len(rh.passing)}/{rh.total} risks flag-free'
        f' · {len(unscored)} unscored</div></div>'
        f'<div><span class="sowhat">{_GOALS["risk"]}</span></div>'
        '</div>')

    comp = (
        '<div class="col"><h3>Compliance</h3>'
        f'<div class="col-num">{len(e.graph.controls) - len(no_policy)}/{len(e.graph.controls)}</div>'
        '<div class="col-den">controls tracing to a governing policy — separately, '
        f'{len(e.graph.controls) - len(no_risk)}/{len(e.graph.controls)} map to a named risk</div>'
        '<div class="col-row"><div class="col-k">Worst-aging hygiene</div><div class="col-v">'
        f'<b>{len(stale_ev)}</b> of {n_ev} evidence records stale or missing</div></div>'
        f'<div class="col-row"><div class="col-k">SLA</div><div class="col-v">{_sla_word(len(ev["fresh"]), n_ev)}'
        f' <span class="drv">evidence fresh on cadence: {len(ev["fresh"])}/{n_ev}</span></div></div>'
        f'<div class="col-row"><div class="col-k">Action plans</div><div class="col-v">{len(plans)} finding(s) with no plan</div></div>'
        f'<div><span class="sowhat">{_GOALS["informed"]}</span></div>'
        '</div>')

    self_n = sources.get("self-identified", 0)
    dev_measured = [s for s in dev_sla if s.met is not None]
    ai = (
        '<div class="col"><h3>AI &amp; Op Excellence</h3>'
        f'<div class="col-num">{self_n}/{n_findings}</div>'
        f'<div class="col-den">findings self-identified (of {n_findings} findings — small n, a ratio not a rate)</div>'
        '<div class="col-row"><div class="col-k">Worst-aging hygiene</div><div class="col-v">'
        f'<b>{len(e.manual_evidence())}</b> of {n_ev} evidence records still collected manually</div></div>'
        '<div class="col-row"><div class="col-k">SLA</div><div class="col-v">'
        f'{_sla_word(sum(1 for s in dev_measured if s.met), len(dev_measured))}'
        f' <span class="drv">deviations dispositioned in SLA: '
        f'{sum(1 for s in dev_measured if s.met)}/{len(dev_measured)} measured</span></div></div>'
        '<div class="col-row"><div class="col-k">Automation</div><div class="col-v">roadmap: 7 seams, 0 live '
        '(data + documented seam)</div></div>'
        f'<div><span class="sowhat">{_GOALS["speed"]}</span></div>'
        '</div>')

    return f'<div class="cols">{gov}{risk}{comp}{ai}</div>'


def _program_sla_strip(e: GRCEngine) -> str:
    steps = e.program_sla()
    met = sum(m for m, _ in steps.values())
    measured = sum(n for _, n in steps.values())
    parts = " · ".join(
        f'<span class="part">{_esc(name)}: <b>{m}/{n}</b></span>' for name, (m, n) in steps.items())
    return (
        '<div class="strip">'
        f'<span class="strip-num">{met}/{measured}</span>'
        f'<span class="part"><b>program-wide SLA adherence</b> — measurable process steps currently '
        f'inside their authored service level (sla_config.yaml; denominator: every measurable step '
        f'across the four processes below)</span> {_sla_word(met, measured)}'
        f'<span style="flex-basis:100%"></span>{parts}'
        '</div>'
        '<p class="note">Deliberately <b>no blended health score</b>: a composite of coverage, freshness '
        'and throughput would describe nothing real (P.3). Each figure above keeps its own denominator; '
        'the only aggregate is this like-for-like count of process steps inside their SLA.</p>')


# ---------------------------------------------------------------------------
# Pillar summary cards — the §1.B derivations made visible (drill-down views
# are later specs; this is the landing's supporting detail).
# ---------------------------------------------------------------------------


def _governance_card(e: GRCEngine) -> str:
    pc = e.policy_currency()
    rc = e.requirement_coverage()
    ac = e.agent_coverage()
    rows = "".join(
        f'<tr><td class="nm">{_esc(o.policy_id)}<span class="sub"></span></td>'
        f'<td class="drv">{_esc(o.title)}</td><td>{_fmt_date(o.last_reviewed)}</td>'
        f'<td>{_esc(o.cadence)}</td><td class="num">{_word_over(f"{o.days_overdue}d overdue")}</td></tr>'
        for o in pc.overdue)
    consistency = ("both directions agree" if not rc.mismatched_framework_refs else
                   f"{len(rc.mismatched_framework_refs)} mismatch(es)")
    uncovered = ", ".join(_esc(a) for a in ac.uncovered) or "none"
    return (
        '<div class="card"><h2>Governance</h2>'
        '<p class="sub">Are the commitments current, and does every obligation land on a live control?</p>'
        f'<p class="lede">Policy currency: <b>{pc.current}/{pc.total}</b> policies inside their review '
        f'cadence (denominator: every policy in policies.yaml; cadence per policy, default '
        f'{e.graph.sla.policy_review_cadence_months} months from sla_config.yaml). '
        f'{len(pc.overdue)} overdue:</p>'
        '<table class="tbl"><thead><tr><th>Policy</th><th>Title</th><th>Last reviewed</th>'
        f'<th>Cadence</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>'
        f'<h4>Control-to-requirement coverage</h4>'
        f'<p class="lede"><b>{len(rc.satisfied)}/{rc.total}</b> external requirements '
        '(denominator: every requirement in regulations.yaml — five DORA pillars, three PCI-DSS '
        'requirements) are satisfied by at least one control that exists in controls.yaml. '
        f'Cross-check with the controls\' own <code>framework_refs</code>: {consistency}.</p>'
        f'<h4>Guardrail coverage of detected agents</h4>'
        f'<p class="lede"><b>{len(ac.covered)}/{len(ac.detected)}</b> covered (denominator: the '
        'security-fed detected-agent set in agent_inventory.yaml, not the guardrails\' own applies_to '
        f'— a self-referencing denominator would always read covered). Ungoverned: '
        f'{_word_over("uncovered")} {uncovered}.</p>'
        '</div>')


def _ai_governance_card(e: GRCEngine) -> str:
    by = e.deviations_by()
    sla = e.deviation_sla()
    pe = e.provisional_exposure()
    complete, incomplete = e.ladder_completeness()
    ac = e.agent_coverage()

    disp = " · ".join(f"{k} <b>{v}</b>" for k, v in by["disposition"].items())
    sev = " · ".join(f"{k} <b>{v}</b>" for k, v in by["severity"].items())
    sla_rows = "".join(
        f'<tr><td class="nm">{_esc(s.dev.id)}</td><td class="drv">{_esc(s.dev.guardrail)}</td>'
        f'<td>{_esc(s.dev.severity)}</td><td>{_esc(s.dev.disposition)}</td>'
        f'<td>{_fmt_date(s.due)}</td><td class="num">'
        + (_word_at("in SLA") if s.met else
           (_word_over(f"{s.days_overdue}d overdue") if s.met is False else _word_below("open, in window")))
        + '</td></tr>'
        for s in sla)
    prov_rows = "".join(
        f'<tr><td class="nm">{_esc(c.dev.id)}</td><td class="drv">{_esc(c.dev.guardrail)}</td>'
        f'<td class="drv">{_esc(c.named_risk)}</td>'
        f'<td class="num">{money(c.band.low)}–{money(c.band.high)}</td>'
        f'<td class="drv">{"clamped to bound" if c.clamped else "within bound"}</td></tr>'
        for c in pe.contributions)
    risk_lines = []
    for nid, band in pe.by_risk.items():
        nr = e.graph.named_risks.get(nid)
        app = nr.appetite_threshold if nr else None
        share = f" ({band.mean / app:.0%} of its {money(app)} appetite in expectation)" if app else ""
        risk_lines.append(f'<b>{_esc(nid)}</b>: +{money(band.low)}–{money(band.high)} provisional{share}')
    ladders = (f'<b>{len(complete)}/{len(e.graph.guardrails)}</b> guardrails declare a complete '
               'response ladder (all four rungs)')
    if incomplete:
        ladders += " — " + ", ".join(
            f'{_esc(g)} missing <i>{", ".join(_esc(r) for r in rungs)}</i> {_word_below("incomplete")}'
            for g, rungs in incomplete.items())

    return (
        '<div class="card" style="border:1px dashed var(--status-below)"><h2>AI governance '
        '<span class="st st-below">· WORK IN PROGRESS — newest, least settled</span></h2>'
        '<p class="sub">Governing the guardrails is a governance act — this section lives under '
        'Governance (P.2). Anchored to the NIST AI RMF core functions (Govern, Map, Measure, Manage; '
        'AI RMF 1.0 / NIST AI 100-1, Jan 2023). Autonomy tiers and the Agentic Profile are '
        '<b>Cloud Security Alliance</b> extensions that align with and extend NIST RMF — CSA-attributed, '
        'v1/evolving, not NIST-published. Runtime enforcement defers to an AAGATE-style overlay '
        '(CSA, Dec 2025) — an external executor, not something this repo builds.</p>'
        f'<p class="lede">Guardrail coverage: <b>{len(ac.covered)}/{len(ac.detected)}</b> detected agents '
        f'governed (see Governance card for the denominator). Open deviations — by disposition: {disp}; '
        f'by severity: {sev}.</p>'
        '<h4>Time-to-disposition (the governing-at-speed number)</h4>'
        '<p class="lede">Time to a human <i>disposition</i> of a machine-proposed deviation, against each '
        'guardrail\'s <code>disposition_sla_hours</code> — not time-to-approval-before-action. '
        'Denominator: all five deviation records in guardrail_events/.</p>'
        '<table class="tbl"><thead><tr><th>Deviation</th><th>Guardrail</th><th>Severity</th>'
        f'<th>Disposition</th><th>Due</th><th>Status</th></tr></thead><tbody>{sla_rows}</tbody></table>'
        '<h4>Provisional deviation exposure — Model B overlay (WIP)</h4>'
        '<p class="lede">The per-issue FAIR contribution of each <i>proposed or accepted</i> deviation '
        '(dismissed and remediated contribute nothing), bounded by its guardrail\'s '
        '<code>provisional_move.max_band_90ci</code>, shown as a <b>provisional increment against the '
        'named risk\'s appetite</b>. It is not added to the eng portfolio total and is not that risk\'s '
        'published exposure.</p>'
        '<table class="tbl"><thead><tr><th>Deviation</th><th>Guardrail</th><th>Named risk</th>'
        f'<th>Provisional contribution</th><th>Bound</th></tr></thead><tbody>{prov_rows}</tbody></table>'
        f'<p class="lede" style="margin-top:10px">{" · ".join(risk_lines)}</p>'
        '<div class="callout warn"><b>Deliberate modeling decision — Model B</b> (alongside the v3.4 and '
        'evidence-informed-uncertainty notes): this overlay extends who may write the <i>exposure</i> side '
        'from humans to humans plus a <b>bounded auto-registrar</b>. Appetite stays authored and '
        'machine-untouched. The one-path rule holds: only factor-moving issues move a number — one of '
        'them is now machine-proposed, under bound. The meta-guardrail is <code>provisional_move</code>: '
        'a bounded factor, a mandatory disposition SLA, auto-expiry on decision.</div>'
        f'<h4>Response-ladder completeness</h4><p class="lede">{ladders}.</p>'
        '</div>')


def _risk_card(e: GRCEngine) -> str:
    rh = e.risk_hygiene()
    unscored = e.unscored_risks()
    rem = e.remediation_sla()
    flagged = "".join(
        f'<tr><td class="nm">{_esc(nid)}</td><td class="drv">{", ".join(_esc(c) for c in codes)}</td>'
        f'<td>{_word_below("flagged")}</td></tr>'
        for nid, codes in sorted(rh.flagged.items()))
    kick_rows = "".join(
        f'<tr><td class="nm">{_esc(i.id)}</td><td class="num">&times;{i.renewal_count}</td>'
        f'<td class="drv">{"justification refreshed" if i.justification_changed_last else "justification never revisited"}</td>'
        f'<td>{_word_over("temporary forever") if not i.justification_changed_last else _word_below("renewed")}</td></tr>'
        for i in rem.kicked)
    worst = rem.overdue[:5]
    over_rows = "".join(
        f'<tr><td class="nm">{_esc(r.id)}</td><td class="drv">{_esc(r.title[:52])}</td>'
        f'<td>{_fmt_date(r.target_date)}</td>'
        f'<td class="num">{_word_over(f"{(e.config.as_of - r.target_date).days}d past target")}</td></tr>'
        for r in worst)
    return (
        '<div class="card"><h2>Risk</h2>'
        '<p class="sub">Is the register clean, complete, and moving at the speed it promised?</p>'
        f'<p class="lede">Hygiene pass: <b>{len(rh.passing)}/{rh.total}</b> named risks carry no validation '
        'flags (criteria: the validate_graph flag surface — uncalibrated / unknown / stale estimator, '
        'no-op effect, threshold-over-capacity, threshold-sum — attributed to the risk carrying the '
        'flagged scenario or issue). Diagnostic only; none of this moves residual.</p>'
        '<table class="tbl"><thead><tr><th>Named risk</th><th>Flags</th><th>Status</th></tr></thead>'
        f'<tbody>{flagged}</tbody></table>'
        f'<h4>Unscored</h4><p class="lede"><b>{len(unscored)}</b> named risk(s) with zero scenarios '
        f'(denominator: all {rh.total} named risks): '
        + ", ".join(f'{_esc(n)} {_word_below("unscored")}' for n in unscored)
        + '. Registered and owned, never quantified — the appetite is authored, the exposure is unknown.</p>'
        f'<h4>Remediation SLA</h4>'
        f'<p class="lede"><b>{rem.total_live - len(rem.overdue)}/{rem.total_live}</b> live remediations '
        '(funded, in progress, or proposed) are inside their target date; the worst five overdue:</p>'
        '<table class="tbl"><thead><tr><th>Remediation</th><th>Title</th><th>Target</th><th>Status</th>'
        f'</tr></thead><tbody>{over_rows}</tbody></table>'
        f'<h4>Can-kicking</h4><p class="lede"><b>{len(rem.kicked)}</b> active exceptions renewed '
        f'{e.config.renewal_alert_count}+ times ({len(rem.kicked_unrefreshed)} with the justification never '
        'revisited). This is the process-failure lens; the exposure-ranked deferral view and the starvation '
        'read stay on the eng tab.</p>'
        '<table class="tbl"><thead><tr><th>Exception</th><th>Renewals</th><th>Justification</th>'
        f'<th>Status</th></tr></thead><tbody>{kick_rows}</tbody></table>'
        '</div>')


def _compliance_card(e: GRCEngine) -> str:
    no_policy, no_risk = e.unmapped_controls()
    plans = e.findings_without_plan()
    ev = e.evidence_freshness()
    manual = e.manual_evidence()
    reuse = e.cross_framework_reuse()
    over_eng = e.over_engineered_controls()
    n_controls = len(e.graph.controls)
    n_ev = len(e.graph.evidence)
    plan_rows = "".join(
        f'<tr><td class="nm">{_esc(i.id)}</td><td class="drv">{_esc(i.title[:64])}</td>'
        f'<td>{_esc(i.severity)}</td><td>{_word_over("no action plan")}</td></tr>'
        for i in plans)
    reuse_rows = "".join(
        f'<tr><td class="nm">{_esc(cid)} {_esc(e.graph.controls[cid].title[:40])}</td>'
        f'<td class="drv">{", ".join(_esc(r) for r in rids)}</td>'
        f'<td>{_word_at("reused")}</td></tr>'
        for cid, rids in reuse.items())
    over_rows = "".join(
        f'<tr><td class="nm">{_esc(cid)} {_esc(e.graph.controls[cid].title[:40])}</td>'
        f'<td class="drv">{", ".join(_esc(n) for n in nids)}</td>'
        f'<td>{_word_below("over-controlled")}</td></tr>'
        for cid, nids in over_eng[:8])
    return (
        '<div class="card"><h2>Compliance</h2>'
        '<p class="sub">Is every control mapped, proven, and pulling its weight — and only its weight?</p>'
        '<p class="lede"><b>Unmapped controls, two denominators reported separately</b> (never one '
        f'ambiguous number): <b>{len(no_policy)}/{n_controls}</b> controls trace to no governing '
        f'<i>policy</i> (currently zero by construction), while <b>{len(no_risk)}/{n_controls}</b> map to '
        'no <i>named risk</i> — the expected state of an illustration exercising part of the framework.</p>'
        f'<h4>Findings without an action plan</h4>'
        f'<p class="lede"><b>{len(plans)}</b> of {sum(e.finding_sources().values())} findings have no '
        'remediation whose <code>addresses_issues</code> points at them:</p>'
        '<table class="tbl"><thead><tr><th>Finding</th><th>Title</th><th>Severity</th><th>Status</th>'
        f'</tr></thead><tbody>{plan_rows}</tbody></table>'
        f'<h4>Evidence</h4><p class="lede">Freshness (derived from cadence + last_collected; denominator '
        f'all {n_ev} evidence records): {_word_at("fresh")} <b>{len(ev["fresh"])}</b> · '
        f'{_word_below("stale")} <b>{len(ev["stale"])}</b> ({", ".join(_esc(x) for x in ev["stale"])}) · '
        f'{_word_over("missing")} <b>{len(ev["missing"])}</b> ({", ".join(_esc(x) for x in ev["missing"])}). '
        f'Manual collection: <b>{len(manual)}/{n_ev}</b> ({", ".join(_esc(x) for x in manual)}).</p>'
        '<h4>Cross-framework reuse (a positive finding)</h4>'
        '<p class="lede">Controls satisfying more than one external requirement — map once, satisfy many:</p>'
        '<table class="tbl"><thead><tr><th>Control</th><th>Requirements</th><th>Status</th></tr></thead>'
        f'<tbody>{reuse_rows}</tbody></table>'
        '<h4>Over-engineered controls (two-sided scale — amber, not green)</h4>'
        f'<p class="lede"><b>{len(over_eng)}</b> controls map only to risks sitting BELOW appetite '
        '(over-invested relative to declared tolerance, reusing the eng tab\'s below-appetite signal — '
        '<code>--status-below</code> means over-control on both tabs). Over-control is wasted effort and '
        'friction, a problem, not a healthy state; green here means <i>right-sized</i>, never '
        f'<i>maximal</i>. Distinct from the reuse read above. First eight of {len(over_eng)}:</p>'
        '<table class="tbl"><thead><tr><th>Control</th><th>Mapped risks (all below appetite)</th>'
        f'<th>Status</th></tr></thead><tbody>{over_rows}</tbody></table>'
        '</div>')


# The seven next-steps.md items as an initiative portfolio (§1.B AI & OpEx):
# (title, the metric on this tab it would move). Honest: every stage is
# "data + documented seam", nothing runs live (P.10).
_ROADMAP = [
    ("Automated evidence collection",
     "evidence fresh on cadence (now 10/14) and manual collection (now 5/14)"),
    ("Policy-as-code",
     "control-to-requirement coverage; guardrail assertions already declare the shape"),
    ("Live incident / issue auto-mapping",
     "self-identified share of findings (advisory propose→ratify, never writes unaided)"),
    ("Dynamic intake and triage workflow",
     "risk intake→scored SLA (authored at 10 days; unmeasured until intake exists)"),
    ("Second-order remediation composition & evidence-informed uncertainty",
     "remediation SLA view (a called-out future modeling decision, not a silent add)"),
    ("KRI live ingestion, alerting, trend monitoring",
     "agent-telemetry KRIs (seeded as data; a breach informs re-estimation, never adds a term)"),
    ("Deduplication checks (tier-aware)",
     "issues-floor hygiene (same-issue-twice merges vs same-class-many-instances kept)"),
]

# The build-time hygiene checks behind "% hygiene automated" (§1.B): each row is
# (check, automated?). Deterministic = dates, SLAs, coverage counts — no model.
# The manual rows are the human/ratification steps the same metrics depend on.
_HYGIENE_CHECKS = [
    ("policy review currency (dates vs cadence)", True),
    ("named-risk review currency", True),
    ("evidence freshness (cadence + last_collected)", True),
    ("remediation target-date adherence", True),
    ("deviation disposition SLA", True),
    ("requirement→control existence + two-direction consistency", True),
    ("guardrail coverage of detected agents", True),
    ("estimator calibration staleness (validate_graph)", True),
    ("control↔requirement mapping ratification", False),
    ("deviation disposition decision", False),
    ("appetite & policy review sign-off", False),
    ("manual evidence collection (5 records)", False),
]


def _opex_card(e: GRCEngine) -> str:
    sources = e.finding_sources()
    n = sum(sources.values())
    auto = [c for c, a in _HYGIENE_CHECKS if a]
    src = " · ".join(f"{_esc(k)} <b>{v}</b>" for k, v in sorted(sources.items()))
    road_rows = "".join(
        f'<tr><td class="nm">{i}. {_esc(title)}</td>'
        f'<td>{_word_below("data + seam, not built")}</td>'
        f'<td class="drv">{_esc(metric)}</td></tr>'
        for i, (title, metric) in enumerate(_ROADMAP, start=1))
    check_rows = "".join(
        f'<tr><td class="nm">{_esc(c)}</td><td>'
        + (_word_at("automated at build time") if a else _word_below("human step"))
        + '</td></tr>'
        for c, a in _HYGIENE_CHECKS)
    return (
        '<div class="card"><h2>AI &amp; Operational Excellence</h2>'
        '<p class="sub">Using AI to run GRC — the automation roadmap and the self-reporting maturity. '
        'Governing AI lives under Governance, not here (P.2). Deterministic checks (dates, SLA, coverage '
        '— no model) are separated from AI-assisted steps (mapping, classification, drafting — a model '
        'earns its place); every AI-assisted step is advisory: it proposes, a human ratifies, it never '
        'writes the system of record unaided (P.10).</p>'
        '<h4>Automation roadmap — an initiative portfolio, honest, not shipped</h4>'
        '<table class="tbl"><thead><tr><th>Initiative (docs/next-steps.md)</th><th>Stage</th>'
        f'<th>Metric it would move</th></tr></thead><tbody>{road_rows}</tbody></table>'
        f'<h4>Self-reported vs found</h4><p class="lede">The finding-source three-way (denominator: all '
        f'{n} findings): {src}. <b>Small n</b> — read as a current-state ratio, not a rate; a '
        '<code>grc-review</code> source would be added only if proactive second-line discovery is wanted '
        'as its own category. Never collapsed to a two-way.</p>'
        f'<h4>Hygiene automation</h4><p class="lede"><b>{len(auto)}/{len(_HYGIENE_CHECKS)}</b> of the '
        'hygiene checks behind this tab run deterministically at build time (denominator: the checks '
        'listed — anchored to the real metrics above, not an "hours saved" estimate):</p>'
        '<table class="tbl"><thead><tr><th>Check</th><th>Mode</th></tr></thead>'
        f'<tbody>{check_rows}</tbody></table>'
        '</div>')


def _notes_card(e: GRCEngine) -> str:
    return (
        '<div class="card"><h2>Decisions &amp; next steps for this tab</h2>'
        '<ul style="font-size:13px; line-height:1.7; margin:0; padding-left:18px">'
        '<li><b>Separate page, one-way nav (flagged for review):</b> this tab is its own HTML page with a '
        'link to the eng dashboard; the return link is omitted because the eng page must stay '
        'byte-identical (P.4). True in-page tabbing is deferred until the eng render is refactored into a '
        'fragment, under the same byte-identical gate.</li>'
        '<li><b>Security posture (P.8):</b> this page inherits the eng tab\'s posture — static, read-only, '
        'public, synthetic data; auth/RBAC/rate-limiting intentionally not applicable. <b>Revisit before '
        'deploying if this is ever repointed at real risk data</b>: put auth or Vercel Password Protection '
        'in front first.</li>'
        '<li><b>WCAG contrast (§1.F):</b> verified for the status trio on --bg/--surface '
        '(over 7.11/6.04 · at 8.38/7.12 · below 7.94/6.75 · below-tint 10.05/8.54) — all clear the 4.5:1 '
        'AA normal-text bar, including the 10–12px table labels. The standing contrast item is closed.</li>'
        '<li><b>Pillar drill-downs</b> (full Governance / Risk / Compliance / AI-governance / OpEx views) '
        'are later specs, following the same coverage / hygiene / SLA / so-what grammar.</li>'
        '</ul></div>')


# ---------------------------------------------------------------------------
# Page assembly (§1.D)
# ---------------------------------------------------------------------------


def build_grc_page(e: GRCEngine) -> str:
    body = (
        '<div class="wrap">'
        '<header><div class="eyebrow">Company Corp · GRC program</div>'
        '<h1>GRC program health — is the machine working?</h1>'
        f'<div class="meta">Program view for the GRC Manager · reference date '
        f'{e.config.as_of.isoformat()} · <b>synthetic data</b>, generated from git-native YAML</div>'
        '<div class="navrow">↩ <a href="dashboard.html">Engineering risk dashboard (the eng tab)</a> — '
        'that tab answers "what do I fix and in what order"; this one answers "is the machine that '
        'produces that answer working, and is it keeping pace".</div>'
        '<div class="wip wip-strong"><b>WORK IN PROGRESS</b> — v4.0 Spec 1: landing scorecard and '
        'derivation layer only; pillar drill-downs are later specs. The AI-governance section is the '
        'newest and least settled.'
        '<span class="iso"><b>Isolation guarantee:</b> this tab cannot move the engineering numbers. It '
        'reads additional registers (regulations, SLAs, guardrails, deviations) that the eng build never '
        'opens; guardrail deviations live outside <code>data/issues/</code>, so nothing here enters the '
        'residual. The live eng dashboard is verified byte-identical under this build.</span></div>'
        '</header>'
        + _scorecard(e)
        + _program_sla_strip(e)
        + '<div class="grid">'
        + _governance_card(e)
        + _ai_governance_card(e)
        + _risk_card(e)
        + _compliance_card(e)
        + _opex_card(e)
        + _notes_card(e)
        + '</div>'
        '<footer>Every status marker carries its word — no meaning rides on colour alone. Coverage figures '
        'name their denominators. RAG is conventional for coverage/hygiene/SLA and two-sided for control '
        'right-sizing (over-controlled reads amber). Diagnostics only: nothing on this page moves '
        'residual; the one path into residual remains the exception register on the eng tab. Synthetic '
        'corpus, version-controlled; no workflow engine, no live collectors.</footer>'
        '</div>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        '<title>Company Corp — GRC program health</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&'
        'family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">'
        f'<style>{_CSS}</style></head><body>{body}</body></html>'
    )


def render_grc_to(data_dir: Path, config: Config, out: Path) -> Path:
    """Load the extended corpus, compute the GRC derivations, render the tab."""
    graph = load_grc_graph(data_dir)
    engine = GRCEngine(graph, config)
    out.write_text(build_grc_page(engine))
    return out
