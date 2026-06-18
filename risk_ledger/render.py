"""Rendering primitives. Narrative-first, bands throughout.

The hard rule from the SPEC: never render a single spurious figure. So there is
no ``fmt_point`` for a computed quantity. ``fmt_band`` renders a 90% CI;
``fmt_threshold`` renders an *appetite*, which is a stated input the
organization chose, not an estimate, so showing it as one number is honest.
"""

from __future__ import annotations

import datetime as dt
import html as _html
import re

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


# ---------------------------------------------------------------------------
# Markdown -> HTML (a tiny renderer for the exact subset the reports emit)
# ---------------------------------------------------------------------------
#
# The tool stays pure stdlib + PyYAML, so rather than pull in a Markdown
# dependency we render the handful of constructs the views produce: headings,
# horizontal rules, tables, bullet lists, paragraphs, and inline bold / italic /
# code. Anything unexpected falls through as an escaped paragraph.

_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")


def _inline(text: str) -> str:
    """Escape, then apply inline markdown. Code first so its body is untouched."""
    text = _html.escape(text, quote=False)
    text = _CODE_RE.sub(r"<code>\1</code>", text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    return text


def _split_row(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


def _is_separator(row: str) -> bool:
    return set(row.replace("|", "").replace("-", "").replace(":", "").strip()) == set()


def _render_table(rows: list[str]) -> str:
    header = _split_row(rows[0])
    start = 2 if len(rows) >= 2 and _is_separator(rows[1]) else 1
    thead = "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr>"
    body = []
    for r in rows[start:]:
        cells = _split_row(r)
        body.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
    return f"<table><thead>{thead}</thead><tbody>{''.join(body)}</tbody></table>"


def _is_special(s: str) -> bool:
    return s == "---" or s.startswith("#") or s.startswith("|") or s.startswith("- ")


def markdown_to_html(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "":
            i += 1
        elif s == "---":
            out.append("<hr/>")
            i += 1
        elif s.startswith("#"):
            level = min(len(s) - len(s.lstrip("#")), 6)
            out.append(f"<h{level}>{_inline(s.lstrip('#').strip())}</h{level}>")
            i += 1
        elif s.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            out.append(_render_table(block))
        elif s.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
        else:
            para = [s]
            i += 1
            while i < n and lines[i].strip() and not _is_special(lines[i].strip()):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(out)


_CSS = """
:root { color-scheme: light dark; }
body { font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       max-width: 920px; margin: 2rem auto; padding: 0 1.25rem; color: #1a1a1a; background: #fff; }
h1 { font-size: 1.9rem; margin: 0 0 .25rem; }
h2 { font-size: 1.4rem; margin: 2rem 0 .5rem; border-bottom: 2px solid #eee; padding-bottom: .25rem; }
h3 { font-size: 1.15rem; margin: 1.5rem 0 .4rem; }
p { margin: .6rem 0; }
hr { border: 0; border-top: 1px solid #e3e3e3; margin: 1.75rem 0; }
table { border-collapse: collapse; width: 100%; margin: .75rem 0 1.25rem; font-size: .93rem; }
th, td { border: 1px solid #ddd; padding: .45rem .6rem; text-align: left; vertical-align: top; }
th { background: #f5f6f8; }
tbody tr:nth-child(even) { background: #fafafa; }
code { background: #f0f0f2; padding: .05rem .35rem; border-radius: 3px; font-size: .9em; }
ul { margin: .5rem 0 1rem; }
.over { color: #b00020; font-weight: 700; }
.straddling { color: #b06a00; font-weight: 700; }
.within { color: #0a7d33; font-weight: 700; }
"""


def html_document(body_html: str, title: str = "Exception Risk Report") -> str:
    """Wrap rendered body HTML in a clean, self-contained page (inline CSS)."""
    for cls, label in (
        ("over", "OVER appetite"),
        ("straddling", "STRADDLING appetite"),
        ("within", "within appetite"),
    ):
        body_html = body_html.replace(label, f'<span class="{cls}">{label}</span>')
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        f"<title>{_html.escape(title)}</title>\n"
        f"<style>{_CSS}</style></head>\n"
        f"<body><main>\n{body_html}\n</main></body></html>\n"
    )
