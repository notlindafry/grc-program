"""Hand-rolled SVG for the three report charts: the 2026 exposure arc, the
per-risk appetite ranges, and the drift two-ledgers chart.

Pure Python, no dependency, only rectangles / lines / text. The palette matches
the report (see ``render._CSS``). Geometry is generated from the data, never
hardcoded: a linear value->x map across the plot area, with the axis maximum
rounded up to a clean number above the largest value being plotted. The charts
adapt to whatever the engine produces -- the appetite chart renders one row per
breaching risk, however many there are.

Status is neutral: bars and status labels are a single blue, never a red/amber/
green ramp. The reader gets status from each bar's position against the appetite
line and from the labels themselves, not from colour.

Every figure shown is annualized loss exposure, matching the rest of the report;
the axis title and every appetite-line label say ``annual`` so it cannot be read
as single-loss expectancy.
"""

from __future__ import annotations

import html as _html
import math
from dataclasses import dataclass

from .montecarlo import Band

EN_DASH = "–"
ARROW = "→"

# Palette -- matches the report. Status on the charts is deliberately neutral:
# one blue for bars and status labels, never a red/amber/green ramp.
NEUTRAL = "#5b7a99"
TEXT = "#1a1a1a"
MUTED = "#666"
AXIS = "#ccc"
WHITE = "#fff"


# -- text / number formatting -------------------------------------------------

def _esc(s: object) -> str:
    return _html.escape(str(s), quote=True)


def _num(x: float) -> str:
    """A compact coordinate string (drops a trailing ``.0``)."""
    return f"{round(float(x), 1):.1f}".rstrip("0").rstrip(".")


def _unit(x: float) -> tuple[float, str]:
    ax = abs(x)
    if ax >= 1e6:
        return 1e6, "M"
    if ax >= 1e3:
        return 1e3, "k"
    return 1.0, ""


def compact_money(x: float) -> str:
    """One stated figure for a tight chart label: ``$193M``, ``$15M``.

    No decimals. Appetite is a stated input, so a single figure is honest here --
    the same principle as the report's ``fmt_threshold``, just abbreviated.
    """
    div, suf = _unit(x)
    return f"${round(x / div):,}{suf}"


def range_label(band: Band) -> str:
    """A band's 5th-95th span on one shared unit, abbreviated: ``$119–290M``."""
    div, suf = _unit(band.high)
    return f"${round(band.low / div):,}{EN_DASH}{round(band.high / div):,}{suf}"


# -- axis scaling -------------------------------------------------------------

_NICE_CEILINGS = (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10)
_NICE_STEPS = (1, 2, 2.5, 5, 10)


def _nice(x: float, choices: tuple[float, ...]) -> float:
    if x <= 0:
        return 1.0
    base = 10.0 ** math.floor(math.log10(x))
    for m in choices:
        if x <= m * base * (1 + 1e-9):
            return m * base
    return 10.0 * base


def nice_ceiling(x: float) -> float:
    """Smallest clean number (1/1.5/2/2.5/3/4/5/6/8 x 10^k) at or above ``x``."""
    return _nice(x, _NICE_CEILINGS)


def _axis_ticks(axis_max: float) -> list[float]:
    step = _nice(axis_max / 5.0, _NICE_STEPS)
    ticks: list[float] = []
    t = 0.0
    while t <= axis_max * (1 + 1e-9):
        ticks.append(t)
        t += step
    return ticks


# -- low-level SVG primitives (rectangles, lines, text only) ------------------

def _rect(x, y, w, h, *, fill, stroke=None, stroke_w=1.0, fill_opacity=None, rx=2) -> str:
    parts = [f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(max(w, 0))}" '
             f'height="{_num(h)}" rx="{rx}" fill="{fill}"']
    if fill_opacity is not None:
        parts.append(f' fill-opacity="{fill_opacity}"')
    if stroke is not None:
        parts.append(f' stroke="{stroke}" stroke-width="{stroke_w}"')
    parts.append("/>")
    return "".join(parts)


def _line(x1, y1, x2, y2, *, stroke, stroke_w=1.0, dash=None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{_num(x1)}" y1="{_num(y1)}" x2="{_num(x2)}" y2="{_num(y2)}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}"{d}/>')


def _text(x, y, s, *, cls, anchor="start") -> str:
    return (f'<text x="{_num(x)}" y="{_num(y)}" class="{cls}" '
            f'text-anchor="{anchor}">{_esc(s)}</text>')


def _anchor_for(x, x0, x1) -> str:
    """Keep a centred annotation inside the plot: snap to an edge when near one."""
    span = x1 - x0
    if x <= x0 + 0.18 * span:
        return "start"
    if x >= x1 - 0.18 * span:
        return "end"
    return "middle"


def _svg(width, height, body, *, title) -> str:
    return (
        f'<svg class="rl-chart" role="img" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f"<title>{_esc(title)}</title>"
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{WHITE}"/>'
        + body
        + "</svg>"
    )


# -- chart 1: the 2026 exposure arc -------------------------------------------

@dataclass
class ArcRow:
    label: str
    band: Band
    over_count: int


def exposure_arc_svg(rows: list[ArcRow], appetite: float, *, axis_label: str,
                     appetite_label: str) -> str:
    """Three neutral range bars on one shared linear axis, with a single dashed
    aggregate-appetite line and a per-row ``N over appetite`` status label.

    Everything is neutral blue; status rides on the bars' position against the
    appetite line and on the per-row label text, not on colour.
    """
    W, PAD_L, PAD_R = 720, 152, 132
    PLOT_X0, PLOT_X1 = PAD_L, W - PAD_R
    PLOT_W = PLOT_X1 - PLOT_X0
    TOP, ROW_PITCH, RANGE_GAP, BAR_H = 34, 46, 17, 16

    axis_max = nice_ceiling(max(max(r.band.high for r in rows), appetite))
    plot_bottom = TOP + len(rows) * ROW_PITCH
    axis_y = plot_bottom + 6
    height = axis_y + 40

    def X(v: float) -> float:
        return PLOT_X0 + (v / axis_max) * PLOT_W

    body: list[str] = []

    # Aggregate appetite line, spanning all rows, labelled at the top.
    ax = X(appetite)
    body.append(_line(ax, TOP - 2, ax, plot_bottom, stroke=TEXT, stroke_w=1.3, dash="5 4"))
    body.append(_text(ax, TOP - 12, appetite_label, cls="rl-muted",
                      anchor=_anchor_for(ax, PLOT_X0, PLOT_X1)))

    # One neutral range bar per row.
    for i, row in enumerate(rows):
        bar_top = TOP + i * ROW_PITCH + RANGE_GAP
        mid_y = bar_top + BAR_H / 2
        x_lo, x_hi = X(row.band.low), X(row.band.high)
        body.append(_text(PAD_L - 12, mid_y + 4, row.label, cls="rl-label", anchor="end"))
        body.append(_text((x_lo + x_hi) / 2, bar_top - 5, range_label(row.band),
                          cls="rl-muted", anchor="middle"))
        body.append(_rect(x_lo, bar_top, x_hi - x_lo, BAR_H, fill=NEUTRAL))
        body.append(_text(PLOT_X1 + 9, mid_y + 4, f"{row.over_count} over appetite",
                          cls="rl-status"))

    # Axis line, ticks, and the annualization-bearing title.
    body.append(_line(PLOT_X0, axis_y, PLOT_X1, axis_y, stroke=AXIS))
    for t in _axis_ticks(axis_max):
        tx = X(t)
        body.append(_line(tx, axis_y, tx, axis_y + 4, stroke=AXIS))
        body.append(_text(tx, axis_y + 15, f"{round(t / 1e6):,}", cls="rl-muted", anchor="middle"))
    body.append(_text((PLOT_X0 + PLOT_X1) / 2, axis_y + 32, axis_label,
                      cls="rl-label", anchor="middle"))

    return _svg(W, height, "".join(body), title="2026 annual loss exposure arc")


# -- chart 2: per-risk appetite ranges (small multiples) ----------------------

@dataclass
class AppetitePlot:
    name: str
    current: Band
    current_state: str          # over | straddling
    post: Band | None           # projected post-remediation band
    post_state: str | None      # over | straddling | within
    appetite: float


def _transition(current_state: str, post_state: str | None) -> str:
    """Header transition text: ``over → within``, ``over → still over``
    (``still`` marks a state that did not change). The text and the bars' position
    against the appetite line carry the status; colour does not.
    """
    if post_state is None:
        return current_state
    if post_state == "within":
        word = "within"
    elif post_state == current_state:
        word = f"still {post_state}"
    else:
        word = post_state
    return f"{current_state} {ARROW} {word}"


def appetite_ranges_svg(plots: list[AppetitePlot], *,
                        axis_label: str = "annual loss exposure ($M)") -> str:
    """One mini-plot per breaching risk, each on its own scale (magnitudes differ
    by more than an order of magnitude, so a shared scale would crush the small
    risks). Current band a solid neutral bar, projected band a neutral outline
    (solid vs outline is the realized-vs-projected distinction), and a dashed
    per-risk appetite line across both.

    Because each mini-plot is on its own scale, each carries its own numbered
    x-axis (ticks in $M); the shared axis label sits once at the foot of the chart.
    """
    W, M_PAD_L = 600, 88
    PLOT_X0, PLOT_X1 = M_PAD_L, W - 14
    PLOT_W = PLOT_X1 - PLOT_X0
    HEADER_H, APP_LABEL_H, BAR_H, BAR_GAP = 22, 17, 15, 9
    AXIS_GAP, TICK_H, MINI_BOTTOM = 8, 16, 6
    MINI_H = HEADER_H + APP_LABEL_H + 2 * BAR_H + BAR_GAP + AXIS_GAP + TICK_H + MINI_BOTTOM
    OUTER_TOP, MINI_GAP, AXIS_LABEL_H, OUTER_BOTTOM = 8, 14, 22, 6

    stacked = OUTER_TOP + len(plots) * MINI_H + max(len(plots) - 1, 0) * MINI_GAP
    height = stacked + AXIS_LABEL_H + OUTER_BOTTOM
    body: list[str] = []

    for k, plot in enumerate(plots):
        y0 = OUTER_TOP + k * (MINI_H + MINI_GAP)
        highs = [plot.current.high, plot.appetite]
        if plot.post is not None:
            highs.append(plot.post.high)
        axis_max = nice_ceiling(max(highs))

        def X(v: float, _axis_max=axis_max) -> float:
            return PLOT_X0 + (v / _axis_max) * PLOT_W

        cur_top = y0 + HEADER_H + APP_LABEL_H
        after_top = cur_top + BAR_H + BAR_GAP
        axis_y = after_top + BAR_H + AXIS_GAP

        # Header: risk name, a colon, a tab, then the (neutral) transition.
        trans_text = _transition(plot.current_state, plot.post_state)
        body.append(
            f'<text x="0" y="{_num(y0 + 15)}" class="rl-label" text-anchor="start">'
            f'{_esc(plot.name)}:<tspan dx="20" class="rl-status">{_esc(trans_text)}</tspan></text>'
        )

        # Current residual: a solid neutral bar.
        body.append(_text(PLOT_X0 - 8, cur_top + BAR_H / 2 + 4, "current",
                          cls="rl-muted", anchor="end"))
        body.append(_rect(X(plot.current.low), cur_top,
                          X(plot.current.high) - X(plot.current.low), BAR_H, fill=NEUTRAL))

        # Projected residual: an outline bar (light tint). Solid vs outline -- not
        # colour -- is the realized-vs-projected distinction.
        if plot.post is not None:
            body.append(_text(PLOT_X0 - 8, after_top + BAR_H / 2 + 4, "after plan",
                              cls="rl-muted", anchor="end"))
            body.append(_rect(X(plot.post.low), after_top,
                              X(plot.post.high) - X(plot.post.low), BAR_H,
                              fill=NEUTRAL, fill_opacity=0.12, stroke=NEUTRAL, stroke_w=1.5))

        # Dashed appetite line, down to the axis, labelled with the annual figure.
        ax = X(plot.appetite)
        body.append(_line(ax, cur_top - 3, ax, axis_y, stroke=TEXT, stroke_w=1.3, dash="5 4"))
        body.append(_text(ax, y0 + HEADER_H + 12, f"annual appetite {compact_money(plot.appetite)}",
                          cls="rl-muted", anchor=_anchor_for(ax, PLOT_X0, PLOT_X1)))

        # This mini-plot's own x-axis: its own scale, so its own tick numbers ($M).
        body.append(_line(PLOT_X0, axis_y, PLOT_X1, axis_y, stroke=AXIS))
        for t in _axis_ticks(axis_max):
            tx = X(t)
            body.append(_line(tx, axis_y, tx, axis_y + 4, stroke=AXIS))
            body.append(_text(tx, axis_y + 14, f"{round(t / 1e6):,}", cls="rl-muted", anchor="middle"))

    # One shared axis label at the foot: the unit is common; only the scale differs.
    body.append(_text((PLOT_X0 + PLOT_X1) / 2, stacked + 14, axis_label,
                      cls="rl-label", anchor="middle"))

    return _svg(W, height, "".join(body), title="Per-risk appetite ranges, current vs after plan")


# -- chart 3: drift two-ledgers (reported vs true OKR footprint) ---------------

def drift_ledgers_svg(okr_name, internal, true_band, *,
                      axis_label: str = "annual loss exposure ($M)") -> str:
    """Two neutral range bars on one shared linear axis: an OKR's footprint *on
    its own ledger* (the ``internal`` band) and its *true* footprint (the
    ``true_band`` -- internal plus the external risk it pushed onto starved
    teams). Each bar spans its band's 5th-95th percentile.

    The solid full bar is the reality; the on-ledger bar is the same neutral blue
    at reduced opacity, the partial view the OKR's own register shows. Solid vs
    outline already means realized-vs-projected on the appetite chart, and neither
    bar here is a projection, so the distinction is fill opacity, not outline.

    The rightward shift of the true bar carries the externality; the bands do not
    add to a to-the-dollar waterfall (see docs/methodology.md), so the gap is not
    drawn, labelled, or summed -- the two bars and their own ranges are the chart.
    """
    rows = [
        ("on its own ledger", internal, 0.55),
        ("true footprint", true_band, None),
    ]
    W, PAD_L, PAD_R = 720, 152, 24
    PLOT_X0, PLOT_X1 = PAD_L, W - PAD_R
    PLOT_W = PLOT_X1 - PLOT_X0
    TOP, ROW_PITCH, RANGE_GAP, BAR_H = 34, 46, 17, 16

    axis_max = nice_ceiling(max(true_band.high, internal.high))
    plot_bottom = TOP + len(rows) * ROW_PITCH
    axis_y = plot_bottom + 6
    height = axis_y + 40

    def X(v: float) -> float:
        return PLOT_X0 + (v / axis_max) * PLOT_W

    body: list[str] = []

    # One neutral range bar per ledger: the on-ledger bar faded, the true bar solid.
    for i, (label, b, opacity) in enumerate(rows):
        bar_top = TOP + i * ROW_PITCH + RANGE_GAP
        mid_y = bar_top + BAR_H / 2
        x_lo, x_hi = X(b.low), X(b.high)
        mid_x = (x_lo + x_hi) / 2
        body.append(_text(PAD_L - 12, mid_y + 4, label, cls="rl-label", anchor="end"))
        body.append(_text(mid_x, bar_top - 5, range_label(b),
                          cls="rl-muted", anchor=_anchor_for(mid_x, PLOT_X0, PLOT_X1)))
        body.append(_rect(x_lo, bar_top, x_hi - x_lo, BAR_H, fill=NEUTRAL, fill_opacity=opacity))

    # Axis line, ticks, and the annualization-bearing title.
    body.append(_line(PLOT_X0, axis_y, PLOT_X1, axis_y, stroke=AXIS))
    for t in _axis_ticks(axis_max):
        tx = X(t)
        body.append(_line(tx, axis_y, tx, axis_y + 4, stroke=AXIS))
        body.append(_text(tx, axis_y + 15, f"{round(t / 1e6):,}", cls="rl-muted", anchor="middle"))
    body.append(_text((PLOT_X0 + PLOT_X1) / 2, axis_y + 32, axis_label,
                      cls="rl-label", anchor="middle"))

    return _svg(W, height, "".join(body), title=f"{okr_name}: reported vs true footprint")
