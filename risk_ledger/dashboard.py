"""The hero artifact: an executive dashboard for a VP of Engineering (SPEC §6, §7).

Rendered from the derived graph and the engine, as a single self-contained dark
HTML page: a portfolio summary (the ten-second read) plus a **closed set of seven
views** and one worked AI example. No JS framework; charts are baked SVG. The
brand is the vibe-shelf design system adapted for a read-only report (SPEC §7):
dark surfaces, sage accent, Inter/Space Grotesk, flat, with the RAG status triad
held outside the five-colour palette and used only on risk indicators, never on
chrome, never colour-alone.

The set is closed at seven (SPEC v2.7 §8). The six-view ceiling held from Day 4
covered only the *breach-shaped* problems; view 2 ("Where you're over-investing")
was the one missing problem class — over-control — not scope creep. A view earns
its place by mapping to a question a VP actually asks; do not add an eighth unless
one genuinely does.
"""

from __future__ import annotations

import datetime as dt
import html as _html
import math
from pathlib import Path

from .config import Config
from .graph import Graph
from .graph_engine import GraphEngine
from .graph_views import build_drift, flagged_renewals, slipped_remediations
from .loader import load_graph
from .render_svg import nice_ceiling
from .validation import validate_graph

# Every colour is a design-system token, defined once in the ``:root`` block
# below and nowhere else — no raw hex lives in this module outside that block
# (SPEC v2.4 §1). Inline SVG inherits the document's custom properties, and while
# SVG *presentation* attributes (fill="…") can't take var(), the ``style``
# attribute can, so the baked charts reference the same tokens the CSS does.
# Contrast of the status trio and derived muted/faint inks is recorded in
# docs/brand.md (SPEC v2.4 §2).
RAG = {
    "over": ("OVER", "var(--status-over)"),
    "at": ("AT", "var(--status-at)"),
    "below": ("BELOW", "var(--status-below)"),
}


def _esc(s: object) -> str:
    return _html.escape(str(s), quote=True)


def money(x: float) -> str:
    ax = abs(x)
    if ax >= 1e6:
        s = f"${ax / 1e6:.1f}M"
    elif ax >= 1e3:
        s = f"${ax / 1e3:.0f}k"
    else:
        s = f"${ax:.0f}"
    return ("-" + s) if x < 0 else s


def band_str(low: float, high: float) -> str:
    return f"{money(low)}–{money(high)}"


def _article(n: int) -> str:
    """'a'/'an' for a spoken integer — 8, 11 and 18 take 'an' ('an 8% chance')."""
    return "an" if n in (8, 11, 18) or (str(n).startswith("8") and n >= 80) else "a"


def _pct(p: float) -> str:
    """A probability as a percentage, guarded at the extremes (SPEC v2.8 §6): a
    near-certainty printed as a bare ``100%`` (or a near-impossibility as ``0%``)
    reads like a broken number, so clamp to ``>99%`` / ``<1%`` instead."""
    if p >= 0.995:
        return ">99%"
    if p <= 0.005:
        return "<1%"
    return f"{round(p * 100)}%"


def _dot(state: str, label: bool = True) -> str:
    """A status dot beside a text label — never colour alone (SPEC §7)."""
    name, colour = RAG[state]
    lab = f'<span class="rag-l">{name}</span>' if label else ""
    return f'<span class="rag"><span class="dot" style="background:{colour}"></span>{lab}</span>'


# ---------------------------------------------------------------------------
# Small SVG helpers (dark theme, rectangles / lines / text only)
# ---------------------------------------------------------------------------


def _svg(w: int, h: int, body: str, title: str) -> str:
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
            f'aria-label="{_esc(title)}" style="font-family:var(--font-body)">{body}</svg>')


def _t(x, y, s, *, size=12, fill="var(--text)", anchor="start", weight=400, display=False) -> str:
    # fill is a design-system token, so it rides in `style` (a var() cannot go in
    # the SVG `fill` presentation attribute). `display` switches to the display
    # face for numerals — NOT a monospace font; the design system has none.
    style = f"fill:{fill}" + (";font-family:var(--font-display)" if display else "")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" style="{style}">{_esc(s)}</text>')


def _rect(x, y, w, h, fill, *, rx=None, extra="") -> str:
    r = f' rx="{rx}"' if rx is not None else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{r} style="fill:{fill}"{extra}/>'


def _pct_grid_step(span: float) -> float:
    """A nice gridline step (in appetite-percent points) for an axis of ``span``
    points: the smallest of 10/20/25/50/100 that keeps the line count at most 8."""
    for s in (10.0, 20.0, 25.0, 50.0, 100.0):
        if span / s <= 8:
            return s
    return 100.0


def _pct_axis_bounds(pcts: list[float]) -> tuple[float, float]:
    """View-1 axis bounds, derived from the rendered data, never hard-coded (SPEC
    v2.9 §2): pad the min/max by 5 points, then round outward to the nearest 10.
    The pad is the guaranteed clearance — rounding to 10 alone leaves data at 50.1%
    sitting on a 50% edge. Today this yields 40%–170% (data spans ~53%–156%)."""
    lo = math.floor((min(pcts) - 5.0) / 10.0) * 10.0
    hi = math.ceil((max(pcts) + 5.0) / 10.0) * 10.0
    return lo, hi


def exposure_interval_svg(rows: list[tuple], lo_b: float, hi_b: float) -> str:
    """View 1 as an interval plot, read against appetite (SPEC v2.9 §2). The x-axis
    is **percent of each row's own appetite**, so a single static appetite line at
    100% is shared by every row and the breach mass — the slice past 100% — is
    comparable across rows for the first time. Each row draws its **p5–p95
    interval** tinted by RAG state; the **mean is an interior tick carrying a dollar
    label** (the only absolute magnitude in the chart, and it matches the table's
    residual mean); the slice **beyond 100% is a stronger red** and IS the breach
    mass. The axis does not anchor at 0% — no risk has zero exposure, and the plot
    has no zero-originating marks. rows = [(name, low_pct, mean_pct, high_pct,
    state, p_exceed, mean_usd)]; bounds ``lo_b``/``hi_b`` are appetite-percent."""
    left, right, top = 172, 104, 8
    row_h, gap = 34, 10
    axis_h, caption_h = 16, 18
    plot_w = 640 - left - right
    plot_bottom = top + len(rows) * (row_h + gap)
    h = plot_bottom + axis_h + caption_h
    span = hi_b - lo_b

    def x(v):
        return left + plot_w * (v - lo_b) / span

    body = [_rect(0, 0, 640, h, "var(--surface)")]
    # Percent gridlines; 100 is handled separately as the appetite line so it is
    # never drawn (or labelled) as a bare "100%".
    step = _pct_grid_step(span)
    v = math.ceil(lo_b / step) * step
    while v <= hi_b + 1e-6:
        if abs(v - 100.0) > 1e-6:
            body.append(f'<line x1="{x(v):.1f}" y1="{top}" x2="{x(v):.1f}" y2="{plot_bottom}" style="stroke:var(--border)" stroke-width="1"/>')
            body.append(_t(x(v), plot_bottom + 12, f"{int(round(v))}%", size=10, fill="var(--text-muted)", anchor="middle"))
        v += step
    # The one appetite line, at 100% of every row's own appetite (SPEC v2.9 §2).
    xa = x(100.0)
    body.append(f'<line x1="{xa:.1f}" y1="{top}" x2="{xa:.1f}" y2="{plot_bottom}" '
                f'style="stroke:var(--text-strong)" stroke-width="1.25" stroke-dasharray="3 2" opacity="0.85"/>')
    body.append(_t(xa, plot_bottom + 12, "appetite", size=10, fill="var(--text-muted)", anchor="middle"))
    ivh = 12
    for i, (name, low, mean, high, state, p_exc, mean_usd) in enumerate(rows):
        y = top + i * (row_h + gap)
        cy = y + row_h / 2
        colour = RAG[state][1]
        ivy = cy - ivh / 2
        x0, x1 = x(low), x(high)
        body.append(_t(left - 10, cy + 4, name, size=12, anchor="end"))
        # the p5–p95 interval is the mark, RAG-tinted, with a defining outline
        body.append(f'<rect x="{x0:.1f}" y="{ivy:.1f}" width="{max(x1 - x0, 3):.1f}" height="{ivh}" rx="5" '
                    f'style="fill:{colour};stroke:{colour}" fill-opacity="0.32" stroke-opacity="0.9" stroke-width="1"/>')
        # the slice beyond the appetite line (100%) is the breach mass — stronger red
        if high > 100.0:
            xs = max(xa, x0)
            body.append(f'<rect x="{xs:.1f}" y="{ivy:.1f}" width="{max(x1 - xs, 1):.1f}" height="{ivh}" rx="0" '
                        f'style="fill:var(--status-over)" fill-opacity="0.58"/>')
        # the mean tick, carrying its dollar figure — the only absolute magnitude
        # in the chart, and the number the colour keys off
        body.append(f'<line x1="{x(mean):.1f}" y1="{cy - 9:.1f}" x2="{x(mean):.1f}" y2="{cy + 9:.1f}" '
                    f'style="stroke:var(--text-strong)" stroke-width="2"/>')
        body.append(_t(x(mean), cy - 12, money(mean_usd), size=9, anchor="middle",
                       fill="var(--text-strong)", weight=600))
        body.append(_t(636, cy + 1, RAG[state][0], size=10, fill=colour, anchor="end", weight=600))
        if p_exc >= 0.10:
            body.append(_t(636, cy + 12, f"{round(p_exc * 100)}% breach", size=9,
                           fill="var(--text-muted)", anchor="end"))
    cap_y = h - 5
    body.append(_t(636, cap_y, "interval = 5–95% · tick = mean ($) · red = breach mass",
                   size=10, fill="var(--text-muted)", anchor="end"))
    return _svg(640, h, "".join(body), "Residual interval (5–95%) as a percent of appetite, by named risk")


def launch_debt_svg(rows: list[tuple], axis_max: float) -> str:
    """View 4: per-launch reported vs true footprint. rows = [(okr, reported, true)].
    The amber overhang is the undeclared risk debt the launch's own ledger hides."""
    left, right, top = 150, 20, 8
    row_h, gap = 30, 14
    plot_w = 640 - left - right
    h = top + len(rows) * (row_h + gap) + 18

    def x(v):
        return left + plot_w * min(v / axis_max, 1.0)

    body = [_rect(0, 0, 640, h, "var(--surface)")]
    for i, (okr, reported, true) in enumerate(rows):
        y = top + i * (row_h + gap)
        body.append(_t(left - 10, y + 13, okr, size=12, anchor="end"))
        # reported (sage) then the undeclared debt (amber) overhang
        body.append(_rect(left, y, max(x(reported) - left, 1), 16, "var(--accent)", rx=4))
        if true > reported:
            body.append(_rect(x(reported), y, max(x(true) - x(reported), 1), 16, "var(--status-below)", rx=4))
            body.append(_t(x(true) + 6, y + 13, "+" + money(true - reported) + " hidden", size=10, fill="var(--status-below-tint)"))
        body.append(_t(left, y + 27, f"reported {money(reported)} · true {money(true)}", size=10, fill="var(--text-muted)"))
    body.append(_rect(left, h - 12, 10, 10, "var(--accent)", rx=2))
    body.append(_t(left + 15, h - 3, "reported footprint", size=10, fill="var(--text-muted)"))
    body.append(_rect(left + 130, h - 12, 10, 10, "var(--status-below)", rx=2))
    body.append(_t(left + 145, h - 3, "undeclared debt (diverted in)", size=10, fill="var(--text-muted)"))
    return _svg(640, h, "".join(body), "Risk debt per launch: reported vs true footprint")


def cankicking_scatter_svg(points: list[tuple], x_max: float, y_max: float) -> str:
    """View 5: exposure (y) vs age in days (x) for temporary-forever exceptions.
    points = [(age_days, exposure, label)]. Top-right = old and expensive."""
    left, right, top, bottom = 56, 96, 16, 46
    w, h = 640, 264

    def px(a):
        return left + (w - left - right) * min(a / x_max, 1.0)

    def py(e):
        return (h - bottom) - (h - bottom - top) * min(e / y_max, 1.0)

    body = [_rect(0, 0, w, h, "var(--surface)")]
    # gridlines + axes
    for f in (0.5, 1.0):
        gy = py(y_max * f)
        body.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{w - right}" y2="{gy:.1f}" style="stroke:var(--border)" stroke-width="1"/>')
        body.append(_t(left - 6, gy + 3, money(y_max * f), size=10, fill="var(--text-muted)", anchor="end"))
    body.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{h - bottom}" style="stroke:var(--border)"/>')
    body.append(f'<line x1="{left}" y1="{h - bottom}" x2="{w - right}" y2="{h - bottom}" style="stroke:var(--border)"/>')
    for f in (0.5, 1.0):
        body.append(_t(px(x_max * f), h - bottom + 15, f"{int(x_max * f)}d", size=10, fill="var(--text-muted)", anchor="middle"))
    body.append(_t(left, top - 4, "exposure ↑", size=10, fill="var(--text-muted)"))
    body.append(_t((left + w - right) / 2, h - 6, "age since filed (days) →", size=10, fill="var(--text-muted)", anchor="middle"))
    # place labels with greedy vertical de-collision so near-coincident points stay legible
    placed: list[tuple[float, float, float]] = []  # (x0, x1, baseline_y)
    for age, exp, label in sorted(points, key=lambda p: (py(p[1]), px(p[0]))):
        cx, cy = px(age), py(exp)
        body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill-opacity="0.85" stroke-width="1.5" '
                    f'style="fill:var(--status-below);stroke:var(--surface)"/>')
        w_est = len(label) * 5.6 + 12
        to_left = cx + 12 + w_est > w - 4
        anchor = "end" if to_left else "start"
        lx0, lx1 = (cx - 12 - w_est, cx - 12) if to_left else (cx + 12, cx + 12 + w_est)
        ly = cy + 3
        while any(not (lx1 < p0 or lx0 > p1) and abs(ly - by) < 13 for p0, p1, by in placed):
            ly += 14
        placed.append((lx0, lx1, ly))
        lead_x = cx - 8 if to_left else cx + 8
        if abs(ly - (cy + 3)) > 6:  # leader line when the label was nudged away
            body.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{lead_x:.1f}" y2="{ly - 3:.1f}" style="stroke:var(--text-muted)" stroke-width="0.75" opacity="0.6"/>')
        body.append(_t(cx + (-12 if to_left else 12), ly, label, size=10, anchor=anchor))
    return _svg(w, h, "".join(body), "Can-kicking: exposure versus age of deferral")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _okr_name(graph: Graph, okr_id: str) -> str:
    """The OKR's real name — its title if authored, else the id itself. The id
    (``gcloud-migration``) is the accepted display form (SPEC v2.4 §3.5); this
    never applies a cosmetic ``.title()`` filter."""
    okr = graph.okrs.get(okr_id)
    return okr.title if okr and okr.title else okr_id


def _addressed_by_funded(graph: Graph, scenario_ids: list[str]) -> bool:
    funded = {"funded", "in_progress"}
    rem_ids = {rid for sid in scenario_ids for rid in graph.remediations_of_scenario.get(sid, [])}
    return any(r.status in funded for r in graph.remediations if r.id in rem_ids)


def _rag_counts_html(rag_counts: dict) -> str:
    """The domain's RAG mix as counted dots — every count carries its number, so
    identity is never colour-alone (SPEC §7). Zeros stay, faint, to keep the read."""
    parts = []
    for state in ("over", "at", "below"):
        n = rag_counts.get(state, 0)
        op = "" if n else ' style="opacity:.3"'
        parts.append(f'<span class="ragc"{op}><span class="dot" style="background:{RAG[state][1]}"></span>{n}</span>')
    return '<span class="ragcs">' + "".join(parts) + "</span>"


def _domain_idle(rollup, residuals: dict):
    """Idle tolerance and allocation status for a domain (SPEC v2.8 §3). Idle is a
    real quantity — `Σ (appetite − residual)` over the domain's BELOW-state risks
    only — that averages nothing, unlike the residual/appetite ratio it replaces
    (a Simpson's trap: Resilience's 59% blended a 102% breach with a 6% idle risk).

    Status is the sharper, actionable finding:
      * ``over-controlled`` — nothing at or above appetite anywhere (pure idle).
      * ``mis-allocated``   — a breach AND idle tolerance in the same domain.
      * ``balanced``        — a risk operating at appetite, no breach.
    """
    belows = [residuals[n] for n in rollup.named_risk_ids if residuals[n].state == "below"]
    overs = [residuals[n] for n in rollup.named_risk_ids if residuals[n].state == "over"]
    idle = sum(r.threshold - r.band.mean for r in belows)
    biggest = max(belows, key=lambda r: r.threshold - r.band.mean, default=None)
    rc = rollup.rag_counts
    if rc.get("over", 0) >= 1 and rc.get("below", 0) >= 1:
        status = "mis-allocated"
    elif rc.get("over", 0) == 0 and rc.get("at", 0) == 0:
        status = "over-controlled"
    else:
        status = "balanced"
    return idle, overs, biggest, status


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _summary(graph: Graph, eng: GraphEngine) -> str:
    p = eng.portfolio()
    over = [r for r in eng.all_named_risk_residuals() if r.state == "over"]
    over.sort(key=lambda r: r.band.mean, reverse=True)
    orphans = [r for r in over if not _addressed_by_funded(graph, r.scenario_ids)]
    n_renew = len(flagged_renewals(graph, eng.config))
    n_slip = len(slipped_remediations(graph, eng.config))
    # launch carrying the most undeclared debt
    drifts = [build_drift(graph, eng, o) for o in graph.okrs]
    drifts = [d for d in drifts if d.true and d.has_undeclared_debt]
    drifts.sort(key=lambda d: (d.true.mean - (d.reported.mean if d.reported else 0)), reverse=True)
    launch = drifts[0] if drifts else None
    # over-investing is a problem too (SPEC v2.7 §3): the over-controlled domain is
    # the one with nothing at or above appetite, reported by its idle dollars (a
    # real quantity, not the Simpson's-trap ratio, SPEC v2.8 §3).
    residuals = {r.named_risk.id: r for r in eng.all_named_risk_residuals()}
    oc, oc_idle = None, 0.0
    ma, ma_idle, ma_overs = None, -1.0, []
    for d in eng.all_domain_rollups():
        idle, overs, _big, status = _domain_idle(d, residuals)
        if status == "over-controlled" and idle > oc_idle:
            oc, oc_idle = d, idle
        elif status == "mis-allocated" and idle > ma_idle:
            ma, ma_idle, ma_overs = d, idle, overs

    pos = RAG[p.appetite_state]
    cards = []
    cards.append(
        f'<div class="hero"><div class="hero-num" style="color:{pos[1]}">{band_str(p.band.low, p.band.high)}</div>'
        f'<div class="hero-cap">residual exposure this year, against a {money(p.appetite)} appetite'
        f' &nbsp;{_dot(p.appetite_state)}</div>'
        f'<div class="hero-sub">Over appetite — the signal: '
        f'{"the entire residual range sits above the " + money(p.appetite) + " line" if p.p_over_appetite >= 0.99 else _pct(p.p_over_appetite) + " of the range is over the line"}. '
        f'Roughly {_article(round(p.p_over_capacity * 100))} '
        f'<b style="color:var(--status-below-tint)">{_pct(p.p_over_capacity)} chance</b> of crossing the '
        f'{money(p.capacity)} materiality line this year. '
        f'{round(p.band.mean / graph.enterprise.revenue_annual * 1000) / 10}% of revenue.</div></div>'
    )
    # Four peer tiles, four genuinely different asks (SPEC v2.9 §5). "Top fixes"
    # (over[:3], a table of contents for the chart six inches below) and "Falling
    # through cracks" (both orphans are already mis-allocation drivers) are gone;
    # mis-allocation leads because it is the sharpest read — the money to cover a
    # breach is already sitting idle in the same domain, under the same owner.
    # Over-control does NOT fold in: Privacy has nothing at or above appetite, so
    # there is no breach to reallocate toward — it keeps its own slot.
    ma_over = ", ".join(o.named_risk.label for o in ma_overs) if ma_overs else "—"
    tiles = [
        ("Mis-allocated", ma.domain.title if ma else "—",
         (f"{money(ma_idle)} idle beside a breach ({ma_over}) — same owner can reallocate it"
          if ma else "—"), True),
        ("Over-controlled", oc.domain.title if oc else "—",
         (f"{money(oc_idle)} idle — nothing at or above appetite" if oc else "—"), True),
        ("Riding a launch", _okr_name(graph, launch.okr) if launch else "—",
         (f"+{money(launch.true.mean - launch.reported.mean)} undeclared debt on {_okr_name(graph, launch.okr)}" if launch else "no diverted debt"), False),
        ("The can you keep kicking", f"{n_renew} renewed · {n_slip} slipped",
         "temporary-forever + slipped dates", False),
    ]
    tile_html = "".join(
        f'<div class="tile{" warn" if warn else ""}"><div class="tile-k">{_esc(k)}</div>'
        f'<div class="tile-v">{_esc(v)}</div><div class="tile-s">{_esc(s)}</div></div>'
        for k, v, s, warn in tiles
    )
    return (f'<section class="summary"><h2>Where are we weakest, what do we fix first, '
            f'and why does it matter to what&nbsp;we\'re&nbsp;shipping?</h2>{cards[0]}'
            f'<div class="tiles">{tile_html}</div></section>')


def _view1_key(r) -> tuple:
    """Rank/select by position against appetite, not by absolute dollars (SPEC v2.9
    §3/§4): ``(-round(100·mean/appetite), -p_exceed)``. Rounding to the displayed
    precision **before** comparing is not cosmetic — the raw top-two ratio gap
    (103.2% vs 102.9%) is inside the Monte Carlo's own noise, so a raw key lets the
    seed decide row 1. Rounded, the three OVER risks lock to Platform > PCI >
    Production across seeds; the AT block still shuffles, which is correct — the
    model cannot tell risks 2.8 points apart, and asserting an order would describe
    nothing."""
    return (-round(100 * r.band.mean / r.threshold), -r.p_over_appetite)


def _view1(graph: Graph, eng: GraphEngine) -> str:
    ranked = sorted(eng.all_named_risk_residuals(), key=_view1_key)[:8]
    rows = [(r.named_risk.label, 100 * r.band.low / r.threshold, 100 * r.band.mean / r.threshold,
             100 * r.band.high / r.threshold, r.state, r.p_over_appetite, r.band.mean)
            for r in ranked]
    lo_b, hi_b = _pct_axis_bounds([p for row in rows for p in (row[1], row[3])])
    items = []
    for r in ranked:
        drivers = ", ".join(c.issue.id for c in r.drivers[:2]) or "baseline exposure"
        funded = "funded plan" if _addressed_by_funded(graph, r.scenario_ids) else "no funded plan"
        # Position and probability, side by side but never conflated (SPEC v2.5 §2b/§2a):
        # mean/appetite distinguishes a mild amber from the standout; P(exceed) is the tail.
        ratio = f"{round(r.band.mean / r.threshold * 100)}% of appetite"
        pexc = f" · {_pct(r.p_over_appetite)} chance of breach" if r.p_over_appetite >= 0.10 else ""
        items.append(
            f'<tr><td>{_dot(r.state)}</td><td class="nm" title="{_esc(r.named_risk.title)}">{_esc(r.named_risk.label)}</td>'
            f'<td class="num">{band_str(r.band.low, r.band.high)}</td>'
            f'<td class="num">{money(r.threshold)}</td>'
            f'<td class="drv">{_esc(ratio)}{pexc}</td>'
            f'<td class="drv">{_esc(drivers)} · {funded}</td></tr>')
    return _card(
        "1", "Your biggest exposures now",
        "Named risks by position against their own appetite: the 5–95% interval tinted by state, the mean as an interior tick with its dollar figure, and the slice past the appetite line (red) as the breach mass.",
        exposure_interval_svg(rows, lo_b, hi_b)
        + f'<table class="tbl"><thead><tr><th></th><th>Named risk</th><th class="num">Residual (90% CI)</th>'
        f'<th class="num">Appetite</th><th>Position</th><th>Driven by</th></tr></thead><tbody>{"".join(items)}</tbody></table>')


_DOM_STATUS = {  # (label, RAG-token colour, row-highlight class)
    "over-controlled": ("OVER-CONTROLLED", "var(--status-below)", " class=\"row-amber\""),
    "mis-allocated": ("MIS-ALLOCATED", "var(--status-over)", ""),
    "balanced": ("Balanced", "var(--status-at)", ""),
}
_DOM_ORDER = {"over-controlled": 0, "mis-allocated": 1, "balanced": 2}


def _view_domains(graph: Graph, eng: GraphEngine) -> str:
    """View 2 (SPEC v2.8 §3): the over-investment / mis-allocation view, and the
    only place Tier 1 (domains) appears. The v2.7 residual/appetite ratio is gone
    — it was a Simpson's trap that averaged a breach and idle headroom into a
    number matching no risk in the domain. Rows rank by **idle tolerance in
    dollars** (`Σ (appetite − residual)` over BELOW-state risks) and carry a status:
    over-controlled (Privacy, nothing near the line) leads; mis-allocated (a breach
    beside idle headroom, the same owner) is the sharper second act."""
    residuals = {r.named_risk.id: r for r in eng.all_named_risk_residuals()}
    data = []
    for d in eng.all_domain_rollups():
        idle, overs, biggest, status = _domain_idle(d, residuals)
        data.append((_DOM_ORDER[status], -idle, d, idle, overs, biggest, status))
    data.sort(key=lambda t: (t[0], t[1]))  # over-controlled first; then by idle desc
    rows = []
    for _, _, d, idle, overs, biggest, status in data:
        label, colour, rowcls = _DOM_STATUS[status]
        if status == "mis-allocated":
            ov = ", ".join(o.named_risk.label for o in overs)
            detail = (f"<b>{_esc(ov)}</b> breached, yet <b>{money(idle)}</b> sits idle"
                      + (f" on {_esc(biggest.named_risk.label)}" if biggest else ""))
        elif status == "over-controlled":
            detail = f"nothing at or above appetite anywhere — <b>{money(idle)}</b> idle across {d.rag_counts['below']} risks"
        else:
            detail = "a risk operating at appetite, no breach"
        pill = (f'<span class="rag"><span class="dot" style="background:{colour}"></span>'
                f'<span class="rag-l" style="color:{colour}">{label}</span></span>')
        rows.append(
            f'<tr{rowcls}><td class="nm">{_esc(d.domain.title)}</td>'
            f'<td class="num">{money(idle)}</td>'
            f'<td>{pill}</td>'
            f'<td class="drv">{detail}</td>'
            f'<td>{_rag_counts_html(d.rag_counts)}</td></tr>')
    total_thr = sum(nr.appetite_threshold or 0 for nr in graph.named_risks.values())
    app = eng.portfolio().appetite
    flag = (f'<p class="chain">Bottom-up appetite totals <b>{money(total_thr)}</b> against a {money(app)} declared '
            f'enterprise appetite (<b>{total_thr / app:.2f}×</b>). Either the risk-level thresholds are generous, '
            f'or the enterprise line is not what the business actually tolerates.</p>')
    inner = (f'<p class="lede">Declared tolerance sitting <i>idle</i> — control effort spent below the line you set '
             f'is effort not spent shipping. <b>Over-controlled</b> is a domain with nothing at or above appetite; '
             f'<b>mis-allocated</b> is a breach and idle headroom in the same domain, under the same owner — a '
             f'reallocation, not a ratio. Ranked by idle dollars on below-appetite risks. RAG mix is over / at / '
             f'below, each with its count.</p>'
             f'<table class="tbl"><thead><tr><th>Domain (Tier 1)</th><th class="num">Idle tolerance</th>'
             f'<th>Status</th><th>What it means</th><th>Risk mix (R/G/A)</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table>{flag}')
    return _card("2", "Where you're over-investing — and mis-allocating",
                 "Domains ranked by idle tolerance: over-controlled where nothing is near the line, mis-allocated where a breach sits beside idle headroom.",
                 inner)


def _view2(graph: Graph, eng: GraphEngine) -> str:
    over = [r for r in eng.all_named_risk_residuals() if r.state == "over"]
    orphans = [r for r in over if not _addressed_by_funded(graph, r.scenario_ids)]
    orphans.sort(key=lambda r: r.band.mean, reverse=True)
    if not orphans:
        inner = '<p class="empty">No orphans — every over-appetite risk has a funded plan.</p>'
    else:
        rows = "".join(
            f'<tr><td>{_dot(r.state)}</td><td class="nm" title="{_esc(r.named_risk.title)}">{_esc(r.named_risk.label)}</td>'
            f'<td class="num">{band_str(r.band.low, r.band.high)}</td>'
            f'<td>{_esc(r.named_risk.owner)}</td>'
            f'<td class="drv">{_pct(r.p_over_threshold)} chance over its {money(r.threshold)} appetite</td></tr>'
            for r in orphans)
        inner = (f'<p class="lede">Real exposure over appetite with <b>no funded remediation</b> behind it — '
                 f'the exposure the exception lens alone would miss.</p>'
                 f'<table class="tbl"><thead><tr><th></th><th>Named risk</th><th class="num">Residual</th>'
                 f'<th>Owner</th><th>Why it matters</th></tr></thead><tbody>{rows}</tbody></table>')
    return _card("3", "Falling through the cracks", "Orphans: over appetite, not accepted, no funded plan.", inner)


_STATE_RANK = {"over": 0, "at": 1, "below": 2}
_HEALTH_RANK = {"red": 0, "amber": 1, "green": 2}


def _view3(graph: Graph, eng: GraphEngine) -> str:
    """View 4 (SPEC v2.8 §4): where safeguards are weakest, answered for the VP.
    The Policy column (the auditor's traceability question, wrong reader) is
    replaced by the **named risks each control mitigates and their RAG state** —
    a red control sitting on an over-appetite risk is the entire point. Sorted by
    health AND the worst mapped risk state, so a red control on a breach outranks
    a red control on an idle risk. Policy stays in the model and validation, and
    the traceability claim stays in the prose below."""
    residuals = {r.named_risk.id: r for r in eng.all_named_risk_residuals()}

    def worst_state(control):
        states = [residuals[n].state for n in control.mapped_named_risks if n in residuals]
        return min((_STATE_RANK[s] for s in states), default=3)

    unhealthy = sorted(eng.unhealthy_controls(),
                       key=lambda h: (_HEALTH_RANK[h.health], worst_state(h.control)))[:10]
    rows = []
    for h in unhealthy:
        colour = "var(--status-over)" if h.health == "red" else "var(--status-below)"
        ev = h.evidence_status
        note = "clean on findings — but unproven" if h.clean_but_unproven else (
            f"{sum(h.findings_by_severity.values())} finding(s), {h.open_gap_count} accepted gap(s)")
        mapped = sorted((residuals[n] for n in h.control.mapped_named_risks if n in residuals),
                        key=lambda r: _STATE_RANK[r.state])[:2]
        miti = ("; ".join(f'{_esc(r.named_risk.label)} {_dot(r.state)}' for r in mapped)
                or '<span class="mut">—</span>')
        rows.append(
            f'<tr><td><span class="dot" style="background:{colour}"></span> '
            f'<b style="color:{colour}">{h.health.upper()}</b></td>'
            f'<td class="nm">{_esc(h.control.id)} {_esc(h.control.title)}</td>'
            f'<td>evidence: <b>{ev}</b></td><td class="drv">{_esc(note)}</td>'
            f'<td class="drv">{miti}</td></tr>')
    inner = (f'<p class="lede">Control health is derived from open issues <i>and</i> evidence freshness — a '
             f'control can be green on findings but amber because its evidence is stale or missing (the '
             f'provability signal). Each row shows the named risk the control <b>mitigates</b> and its state, so '
             f'a red control on an over-appetite risk is legible at a glance; the two lead for exactly that reason. '
             f'Every control still traces up to a governing policy (kept in the model, not this table).</p>'
             f'<table class="tbl"><thead><tr><th>Health</th><th>Control (ISO 27001:2022)</th><th>Evidence</th>'
             f'<th>Why</th><th>&rarr; Mitigates</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')
    return _card("4", "Where your safeguards are weakest",
                 "Control health with evidence blind spots and the over-appetite risks the weak controls are supposed to hold.", inner)


def _view4(graph: Graph, eng: GraphEngine) -> str:
    drifts = [build_drift(graph, eng, o) for o in graph.okrs]
    drifts = [d for d in drifts if d.true and d.true.mean > 0]
    drifts.sort(key=lambda d: d.true.mean, reverse=True)
    top = drifts[:6]
    axis_max = nice_ceiling(max(d.true.high for d in top)) if top else 1.0
    rows = [(_okr_name(graph, d.okr), d.reported.mean if d.reported else 0, d.true.mean) for d in top]
    # starvation chain
    starved = {}
    for i in graph.issues:
        if i.type == "exception" and i.diverted_to:
            starved.setdefault(i.diverted_to, set()).add(i.okr)
    chain = "; ".join(f"<b>{_esc(dest)}</b> ← {', '.join(sorted(src))}" for dest, src in list(starved.items())[:2])
    inner = (f'<p class="lede">Each launch\'s own ledger shows the risk it accepted directly. Its <i>true</i> '
             f'footprint adds the risk debt from other goals whose work was deferred to fund it '
             f'(<code>diverted_to</code>). The amber overhang is undeclared risk debt.</p>'
             + launch_debt_svg(rows, axis_max)
             + (f'<p class="chain">Starvation chain: {chain}</p>' if chain else ""))
    return _card("5", "Risk riding on your launches and rebuilds",
                 "The launch-centric OKR view: risk debt per major launch/rebuild, and the starvation chain.", inner)


def _view5(graph: Graph, eng: GraphEngine) -> str:
    as_of = eng.config.as_of
    renewed = flagged_renewals(graph, eng.config)
    pts = []
    for e in renewed:
        band = eng.contribution_band(e.id)
        exp = band.mean if band else 0.0
        age = (as_of - e.filed_on).days if e.filed_on else 0
        pts.append((age, exp, f"{e.id.replace('EXC-2026-', '#')} ×{e.renewal_count}"))
    x_max = nice_ceiling(max((a for a, _, _ in pts), default=100))
    y_max = nice_ceiling(max((e for _, e, _ in pts), default=1.0)) or 1.0
    slipped = slipped_remediations(graph, eng.config)[:8]
    srows = "".join(
        f'<tr><td class="nm">{_esc(r.id)}</td><td>{_esc(r.status)}</td>'
        f'<td class="num" style="color:var(--status-over)">{_esc(r.target_date)}</td><td class="drv">{_esc(r.title)}</td></tr>'
        for r in slipped)
    inner = (f'<p class="lede">Chronic deferral: exceptions renewed unchanged past the alert count, and '
             f'remediations whose target date has already slipped. Top-right of the scatter is old and expensive.</p>'
             + cankicking_scatter_svg(pts, x_max, y_max)
             + f'<h4>Slipped remediation target dates ({len(slipped_remediations(graph, eng.config))})</h4>'
             f'<table class="tbl"><thead><tr><th>Remediation</th><th>Status</th><th class="num">Target (past)</th>'
             f'<th>Work</th></tr></thead><tbody>{srows}</tbody></table>')
    return _card("6", "The can you keep kicking",
                 "Chronic deferrals from renewal counts and slipped remediation target dates.", inner)


_TRAJ_ARROW = {"rising": "▲", "receding": "▼", "stable": "▬"}


def _view6(graph: Graph, eng: GraphEngine) -> str:
    emerging = eng.emerging_items()
    erows = "".join(
        f'<tr><td class="nm">{_esc(e.scenario.title)}</td>'
        f'<td class="tag">{"/".join(e.scenario.vectors) or "—"}</td>'
        f'<td class="num">{band_str(e.band.low, e.band.high)}</td>'
        f'<td>{_TRAJ_ARROW.get(e.trajectory, "▬")} {_esc(e.trajectory)}</td>'
        f'<td class="drv">{"would breach appetite" if e.would_breach else "within if promoted"}</td></tr>'
        for e in emerging)
    breached = eng.breached_kris()
    kris = ", ".join(k.kri_id.replace("KRI-", "") for k in breached[:6])
    p = eng.portfolio()
    inner = (f'<p class="lede">The forward-looking line: current managed residual is '
             f'<b style="color:{RAG[p.appetite_state][1]}">over the {money(p.appetite)} appetite</b> while the '
             f'emerging column holds items — wide, moving, AI-vectored — that are not yet appetite-tested. Some '
             f'would breach it if they firmed up; others are receding or would stay within. Kept apart from the '
             f'appetite math (honest uncertainty).</p>'
             f'<table class="tbl"><thead><tr><th>Emerging risk</th><th>Vector</th><th class="num">Wide interval</th>'
             f'<th>Trajectory</th><th>If promoted</th></tr></thead><tbody>{erows}</tbody></table>'
             f'<p class="chain">KRI breaches feeding the horizon ({len(breached)}): {_esc(kris)}…</p>')
    return _card("7", "On the horizon",
                 "Emerging risks with wide bands and trajectory, plus the KRI breaches feeding them.", inner)


def _ai_example(graph: Graph) -> str:
    scn = next((s for s in graph.scenarios.values() if s.incident), None)
    if scn is None:
        return ""
    inc = scn.incident
    return (
        '<section class="card ai"><div class="vhdr"><span class="seam">SHOW-LATER SEAM</span>'
        '<h3>Incident → scenario, mapped by the offline AI step</h3></div>'
        '<p class="lede">A single worked example, not a live feature: a synthetic incident ticket run once '
        'offline through the mapping step (SPEC §8), stored as data. A real incident queue repoints here later.</p>'
        '<div class="ai-flow">'
        f'<div class="ai-col"><div class="ai-k">Input ticket · {_esc(inc.get("ticket_id",""))}</div>'
        f'<div class="ai-v">{_esc(inc.get("description",""))}</div></div>'
        '<div class="ai-arrow">→</div>'
        f'<div class="ai-col"><div class="ai-k">Suggested mapping</div>'
        f'<div class="ai-v">domain <b>{_esc(inc.get("suggested_domain",""))}</b> · risk '
        f'<b>{_esc(inc.get("suggested_named_risk",""))}</b><br>factor '
        f'<b>{_esc(inc.get("suggested_factor",""))}</b> · band <b>{_esc(inc.get("suggested_band",""))}</b></div></div>'
        '<div class="ai-arrow">→</div>'
        f'<div class="ai-col"><div class="ai-k">Resulting entry</div>'
        f'<div class="ai-v"><b>{_esc(scn.id)}</b> — {_esc(scn.title)}<br>'
        f'<span class="mut">mapped_by {_esc(inc.get("mapped_by",""))} on {_esc(inc.get("mapped_on",""))}</span></div></div>'
        '</div></section>')


def _card(num: str, title: str, sub: str, inner: str) -> str:
    return (f'<section class="card"><div class="vhdr"><span class="vnum">{num}</span>'
            f'<div><h3>{_esc(title)}</h3><p class="vsub">{_esc(sub)}</p></div></div>{inner}</section>')


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

# The one place raw hex is allowed to live (SPEC v2.4 §1). This :root block is
# the vibe-shelf design system, verbatim (SPEC §7 / the shared design-system
# rules): five colours, every other shade derived with color-mix(), --danger the
# one reserved warning red. The RAG status triad is the one sanctioned extension
# — held OUTSIDE the five per SPEC §7, used only on risk indicators (dots, bars,
# labels), never on chrome; --status-over IS --danger. Everything else in this
# module — CSS and baked SVG alike — references these tokens through var().
_ROOT = """
:root {
  --bg:#0f120d; --surface:#1d231c; --accent:#7d9b83; --text:#e6e4db; --text-strong:#ffffff;
  --bg-raised:var(--surface);
  --surface-hover:color-mix(in srgb, var(--surface) 84%, var(--accent));
  --text-muted:color-mix(in srgb, var(--text), transparent 40%);
  --text-faint:color-mix(in srgb, var(--text), transparent 58%);
  --border:color-mix(in srgb, var(--accent), transparent 80%);
  --border-strong:color-mix(in srgb, var(--accent), transparent 62%);
  --accent-dim:color-mix(in srgb, var(--accent), transparent 84%);
  --accent-ink:var(--bg);
  --danger:#cf8f83;
  --radius:12px; --radius-sm:8px; --maxw:1000px;
  --font-display:"Space Grotesk", system-ui, sans-serif;
  --font-body:"Inter", system-ui, sans-serif;
  --status-over:var(--danger); --status-at:#5fc07e; --status-below:#cda23e; --status-below-tint:#ddb95f;
  color-scheme: dark;
}
"""

_CSS = _ROOT + """
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text); border-top:3px solid var(--accent);
  font-family:var(--font-body); font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased; }
h1,h2,h3,h4,.hero-num,.tile-v { font-family:var(--font-display); font-weight:600; letter-spacing:-0.01em; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.wrap { max-width:var(--maxw); margin:0 auto; padding:40px 24px 80px; }
header .eyebrow { color:var(--accent); font-size:10.5px; font-weight:600; letter-spacing:0.07em; text-transform:uppercase; }
header h1 { font-size:30px; margin:6px 0 4px; color:var(--text-strong); }
header .meta { color:var(--text-muted); font-size:13.5px; }
.summary { margin:32px 0; }
.summary > h2 { font-size:17px; font-weight:500; color:var(--text); max-width:640px; margin:0 0 16px; }
.hero { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:26px 28px; }
.hero-num { font-size:40px; line-height:1.1; }
.hero-cap { color:var(--text); font-size:15px; margin-top:8px; display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.hero-sub { color:var(--text-muted); font-size:13.5px; margin-top:12px; max-width:720px; }
.tiles { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:14px; }
.tile { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:14px 16px; }
.tile.warn { border-left:3px solid var(--status-below); }
.tile.warn .tile-k { color:var(--status-below-tint); }
.tile-k { color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:0.06em; }
.tile-v { color:var(--text-strong); font-size:17px; margin:6px 0 4px; }
.tile-s { color:var(--text-muted); font-size:12px; }
.ragcs { display:inline-flex; gap:10px; }
.ragc { display:inline-flex; align-items:center; gap:4px; font-size:12px; color:var(--text); font-family:var(--font-display); }
.tbl tr.row-amber td { background:color-mix(in srgb, var(--status-below), transparent 90%); }
.tbl tr.row-amber td:first-child { box-shadow:inset 3px 0 0 var(--status-below); }
.grid { display:grid; gap:20px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:24px 26px; }
.vhdr { display:flex; gap:14px; align-items:flex-start; margin-bottom:14px; }
.vnum { flex:0 0 auto; width:28px; height:28px; border-radius:var(--radius-sm); background:var(--bg); border:1px solid var(--accent);
  color:var(--accent); font-family:var(--font-display); font-weight:600; display:grid; place-items:center; font-size:14px; }
.vhdr h3 { font-size:18px; margin:2px 0 2px; color:var(--text-strong); }
.vsub, .vhdr .vsub { color:var(--text-muted); font-size:13px; margin:0; }
.lede { color:var(--text); font-size:13.5px; margin:0 0 14px; max-width:760px; }
.chain { color:var(--text-muted); font-size:12.5px; margin-top:12px; }
.empty { color:var(--text-muted); }
svg { display:block; margin:6px 0 16px; border-radius:var(--radius-sm); }
table.tbl { width:100%; border-collapse:collapse; font-size:13px; }
.tbl th { text-align:left; color:var(--text-muted); font-weight:500; font-size:11px; text-transform:uppercase;
  letter-spacing:0.04em; padding:6px 10px; border-bottom:1px solid var(--border); }
.tbl td { padding:9px 10px; border-bottom:1px solid var(--border); vertical-align:top; }
.tbl tr:last-child td { border-bottom:none; }
.tbl .num { text-align:right; font-family:var(--font-display); white-space:nowrap; }
.tbl .nm { color:var(--text-strong); }
.tbl .drv { color:var(--text-muted); }
.tbl .pol { color:var(--accent); font-size:12px; }
.tbl .tag { color:var(--status-below-tint); font-size:12px; }
h4 { font-size:13px; color:var(--text); margin:18px 0 8px; }
.rag { display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
.rag-l { font-size:11px; font-weight:600; letter-spacing:0.03em; }
.dot { width:9px; height:9px; border-radius:50%; display:inline-block; flex:0 0 auto; }
.ai .seam { font-size:10px; letter-spacing:0.1em; color:var(--accent-ink); background:var(--accent); padding:3px 8px;
  border-radius:var(--radius-sm); font-weight:700; }
.ai .vhdr { align-items:center; }
.ai-flow { display:grid; grid-template-columns:1fr auto 1fr auto 1fr; gap:12px; align-items:center; margin-top:8px; }
.ai-col { background:var(--bg); border:1px solid var(--border); border-radius:var(--radius-sm); padding:14px; }
.ai-k { color:var(--accent); font-size:11px; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px; }
.ai-v { font-size:12.5px; color:var(--text); }
.ai-v .mut { color:var(--text-muted); font-size:11px; }
.ai-arrow { color:var(--text-muted); font-size:20px; text-align:center; }
footer { margin-top:40px; color:var(--text-muted); font-size:12.5px; border-top:1px solid var(--border); padding-top:18px; }
@media (max-width:720px) { .tiles { grid-template-columns:repeat(2,1fr); } .ai-flow { grid-template-columns:1fr; } .ai-arrow { transform:rotate(90deg); } }
"""


def build_dashboard(graph: Graph, eng: GraphEngine) -> str:
    p = eng.portfolio()
    body = (
        '<div class="wrap">'
        '<header><div class="eyebrow">Company Corp · Technology risk</div>'
        '<h1>GRC portfolio — the ten-second read for VP of Engineering</h1>'
        f'<div class="meta">Executive view for engineering leadership · reference date '
        f'{eng.config.as_of.isoformat()} · <b>synthetic data</b>, generated from git-native YAML</div></header>'
        + _summary(graph, eng)
        + '<div class="grid">'
        + _view1(graph, eng) + _view_domains(graph, eng)
        + _view2(graph, eng) + _view3(graph, eng) + _view4(graph, eng)
        + _view5(graph, eng) + _view6(graph, eng)
        + _ai_example(graph)
        + '</div>'
        '<footer>Every figure is a 90% confidence interval from a light FAIR-shaped Monte Carlo, measured '
        'against an authored appetite; the corpus is synthetic and version-controlled. Appetite is a two-sided '
        'target: <b>at appetite is green, below appetite is amber</b> (unused tolerance), over is red. '
        'One position, one probability. No workflow engine, no live collectors — this is a model of the '
        'operating model, deliberately not a platform.</footer>'
        '</div>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        '<title>Company Corp — GRC portfolio</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&'
        'family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">'
        f'<style>{_CSS}</style></head><body>{body}</body></html>'
    )


def render_to(data_dir: Path, config: Config, out: Path) -> Path:
    graph = load_graph(data_dir)
    validate_graph(graph, config)
    eng = GraphEngine(graph, config)
    out.write_text(build_dashboard(graph, eng))
    return out
