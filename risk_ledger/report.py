"""The full report: top-line synthesis, then the three lenses, then confidence.

Narrative-first. The top line is a generated sentence a busy executive cannot
unsee; everything below backs it with bands.
"""

from __future__ import annotations

import datetime as dt

from .config import Config
from .engine import Engine
from .loader import Corpus
from .render import fmt_band, join_clause, plural
from .views.appetite import render_appetite
from .views.drift import build_footprint, render_drift
from .views.ranked import render_ranked, unified_ranking
from .views.renewals import render_renewals


def _short_risk(rid: str) -> str:
    return rid[len("RISK-"):] if rid.startswith("RISK-") else rid


def _dominant_okr(engine: Engine, corpus: Corpus) -> str | None:
    """The OKR with the largest combined (internal + external) footprint."""
    names: set[str] = set()
    for e in corpus.exceptions:
        if e.okr:
            names.add(e.okr)
        if e.diverted_to:
            names.add(e.diverted_to)
    dominant, best = None, 0.0
    for name in names:
        fp = build_footprint(engine, corpus, name)
        mean = fp.combined_band.mean if fp.combined_band else 0.0
        if mean > best:
            best, dominant = mean, name
    return dominant


def _top_line(engine: Engine, corpus: Corpus, config: Config) -> str:
    dominant = _dominant_okr(engine, corpus)
    residuals = engine.all_residuals()
    n_over = sum(1 for r in residuals if r.state == "over")
    n_straddle = sum(1 for r in residuals if r.state == "straddling")
    post_over = [r.risk.id for r in engine.all_post_remediation() if r.state == "over"]

    sentence = ""
    if dominant:
        sentence += f"The **{dominant}** OKR is the dominant source of newly accepted risk. "

    bits = []
    if n_over:
        bits.append(f"**{plural(n_over, 'risk')} over appetite**")
    if n_straddle:
        bits.append(f"{plural(n_straddle, 'risk')} straddling")
    if bits:
        sentence += join_clause(bits) + " today"
        if n_over and not post_over:
            sentence += "; the funded plan is projected to bring all of them back within appetite. "
        elif n_over:
            names = join_clause([_short_risk(r) for r in post_over])
            sentence += (
                f"; the funded plan is projected to clear all but "
                f"{plural(len(post_over), 'risk')} ({names}), whose fix is not funded. "
            )
        else:
            sentence += ". "
    else:
        sentence += "No tracked risk is over appetite today. "

    sentence += (
        "This reads the accepted-exception and funded-remediation book, not a complete risk register."
    )
    return sentence


def _exposure_arc(engine: Engine, corpus: Corpus, config: Config) -> str:
    entering = engine.date_filtered_portfolio_band(config.year_start)
    mid = engine.portfolio_residual_band()
    exiting = engine.post_remediation_portfolio_band()
    if entering is None or mid is None or exiting is None:
        return ""

    lines = ["## 2026 risk exposure", ""]
    lines.append(
        f"Entering 2026 the book carried **{fmt_band(entering)}** in residual annual loss "
        f"({engine.date_filtered_over_count(config.year_start)} over appetite). Mid-year it stands "
        f"at **{fmt_band(mid)}** ({engine.over_count()} over). If the funded plan executes it exits "
        f"2026 at **{fmt_band(exiting)}** ({engine.post_remediation_over_count()} over). The move "
        f"from entering to exiting is the headline; these bands do not add to a to-the-dollar "
        f"waterfall."
    )
    lines.append("")

    dominant = _dominant_okr(engine, corpus)
    up = "the 2026 acceptances pushed it up"
    if dominant:
        fp = build_footprint(engine, corpus, dominant)
        if fp.combined_band is not None:
            up = f"the 2026 acceptances pushed it up (the {dominant} OKR alone adds {fmt_band(fp.combined_band)})"
    rems = [it for it in unified_ranking(engine, corpus) if it.kind == "remediation"]
    down = "the funded plan pulls it down"
    if rems:
        down = (
            f"the funded plan pulls it down ({plural(len(rems), 'funded remediation')}, the largest "
            f"buying down {fmt_band(rems[0].reduction)})"
        )
    lines.append(f"Two forces move the book: {up}; {down}.")
    lines.append("")

    post_over = [r.risk.id for r in engine.all_post_remediation() if r.state == "over"]
    if post_over:
        names = join_clause(post_over)
        lines.append(
            f"The exit figure is a projection conditional on the funded plan executing; "
            f"{names} {'is' if len(post_over) == 1 else 'are'} projected to remain over, its fix unfunded."
        )
        lines.append("")
    return "\n".join(lines)


def _data_confidence(engine: Engine, corpus: Corpus, config: Config) -> str:
    total = len(corpus.exceptions)
    rejected = [e for e in corpus.exceptions if e.rejected]
    computable = [e for e in corpus.exceptions if e.is_computable]
    # "Calibrated estimators within the refresh window" == no trust flag at all.
    trusted = [e for e in computable if not e.trust_flags]
    untrusted = [e for e in computable if e.trust_flags]
    flagged = [e for e in computable if e.flags]

    lines = ["## Data confidence", ""]
    lines.append(
        f"{len(trusted)} of {total} records rest on calibrated, in-window estimates with explicit "
        f"scope. " + (
            f"{plural(len(untrusted), 'record')} rest on uncalibrated, stale, or vaguely-scoped "
            f"inputs and are excluded from every band until corrected. "
            if untrusted else ""
        ) + (
            f"{plural(len(flagged), 'record')} {'is' if len(flagged) == 1 else 'are'} flagged and held "
            f"out of the rankings until corrected. "
            if flagged else ""
        ) + (
            f"{plural(len(rejected), 'record')} failed a hard gate and {'was' if len(rejected) == 1 else 'were'} "
            f"rejected outright. "
            if rejected else ""
        )
    )
    lines.append("")
    lines.append(
        f"All figures are 90% confidence ranges from a {config.iterations:,}-iteration light Monte "
        f"Carlo (lognormal for frequency and magnitude, logit-normal for probabilities), seeded "
        f"(seed {config.seed}) for a reproducible audit trail. Contributions are summed as "
        f"independent marginal estimates — a deliberate light-fidelity simplification, since real "
        f"effects can interact. Read these as relative magnitudes, not precise valuations."
    )
    lines.append("")
    return "\n".join(lines)


def render_report(engine: Engine, corpus: Corpus, config: Config) -> str:
    records = len(corpus.exceptions)
    okrs = len({e.okr for e in corpus.exceptions if e.okr})
    mapped_risks = sum(1 for rid in corpus.risks if engine.risk_is_computable(rid))

    out = [
        "# Company Corp Exceptions Risk Report",
        "",
        f"**Generated {config.as_of.isoformat()} · Scope: all active exceptions · "
        f"{plural(records, 'record')}, {plural(okrs, 'OKR')}, "
        f"{plural(mapped_risks, 'mapped risk')}**",
        "",
        "---",
        "",
        "## Top line",
        "",
        _top_line(engine, corpus, config),
        "",
        "---",
        "",
    ]

    arc = _exposure_arc(engine, corpus, config)
    if arc:
        out += [arc, "---", ""]

    out += [
        render_drift(engine, corpus, config, significant_only=True),
        "---",
        "",
        render_appetite(engine, corpus, config),
        "---",
        "",
        render_renewals(engine, corpus, config),
        "---",
        "",
        render_ranked(engine, corpus, config),
        "---",
        "",
        _data_confidence(engine, corpus, config),
    ]
    return "\n".join(out).rstrip() + "\n"
