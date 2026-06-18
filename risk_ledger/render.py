"""Rendering primitives. Narrative-first, bands throughout.

The hard rule from the SPEC: never render a single spurious figure. So there is
no ``fmt_point`` for a computed quantity. ``fmt_band`` renders a 90% CI;
``fmt_threshold`` renders an *appetite*, which is a stated input the
organization chose, not an estimate, so showing it as one number is honest.
"""

from __future__ import annotations

import datetime as dt

from .montecarlo import Band

EN_DASH = "–"


def fmt_money(x: float) -> str:
    neg = x < 0
    ax = abs(x)
    if ax >= 1e6:
        s = f"${ax / 1e6:.1f}M"
    elif ax >= 1e3:
        s = f"${ax / 1e3:.0f}k"
    else:
        s = f"${ax:.0f}"
    return ("-" + s) if neg else s


def fmt_band(band: Band) -> str:
    """A money 90% CI, e.g. ``$0.9M–$1.7M``."""
    return f"{fmt_money(band.low)}{EN_DASH}{fmt_money(band.high)}"


def fmt_threshold(x: float) -> str:
    """A stated appetite. A single figure is honest here -- it is an input."""
    return fmt_money(x)


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def quarter_label(d: dt.date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"Q{q} {d.year}"


# Appetite phrasing -----------------------------------------------------------

APPETITE_BADGE = {
    "over": "OVER appetite",
    "straddling": "STRADDLING appetite",
    "within": "within appetite",
}

BAND_POSITION = {
    "over": "the band sits fully above the line",
    "straddling": "the band crosses the line, so whether you are over depends on the high end",
    "within": "the band sits below the line",
}


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """A GitHub-flavoured markdown table."""
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def join_clause(items: list[str]) -> str:
    """Oxford-comma join: ['a'] -> 'a'; ['a','b'] -> 'a and b'; ['a','b','c'] -> 'a, b, and c'."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    if n == 1:
        return f"{n} {singular}"
    return f"{n} {plural_form or singular + 's'}"
