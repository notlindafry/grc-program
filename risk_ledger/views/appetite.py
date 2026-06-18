"""Appetite breach view -- the per-risk lens.

Shows where accumulated acceptances pushed a mapped risk past its stated number,
and whether that was one big call or a thousand small ones. The single-acceptance
vs accumulation distinction is the most useful thing in the view: the first has
an owner to scrutinize, the second is a process problem with no one to blame.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from ..engine import Engine, ResidualResult
from ..loader import Corpus
from ..render import (
    APPETITE_BADGE,
    BAND_POSITION,
    fmt_band,
    fmt_threshold,
    join_clause,
    md_table,
    pct,
    plural,
    raw_svg_block,
)
from ..render_svg import AppetitePlot, appetite_ranges_svg

@dataclass
class Breach:
    kind: str  # "single-acceptance" | "accumulation"
    dominant_share: float
    culprit_id: str | None
    all_tolerable_alone: bool


def classify_breach(engine: Engine, res: ResidualResult) -> Breach | None:
    """Classify an over/straddling breach as single-acceptance or accumulation.

    The rule set, applied in order, over the risk's active trusted contributors:

    1. **Solo-breach rule** (structural, no tunable). If baseline plus any single
       contributor *alone* is ``over`` appetite -- its standalone 90% residual
       sits fully above the line -- that exception is sufficient on its own, so
       the breach is **single-acceptance** and the culprit is the largest such
       exception. Uses the same 90%-band appetite test as everywhere else.

    2. **Dominant-share threshold** (``config.single_acceptance_share``, default
       0.50). If no exception breaches alone but the leading contributor's
       expected contribution is at least this share of the contributed exposure
       (the sum of contributor means, i.e. the exposure added over baseline),
       the breach is **single-acceptance**, culprit = the top contributor.

    3. Otherwise **accumulation**: no single sufficient cause and the exposure is
       spread. ``all_tolerable_alone`` records whether *every* contributor stays
       within appetite on its own -- the death-by-a-thousand-cuts signal.
    """
    if not res.contributors:
        return None
    total = sum(c.band.mean for c in res.contributors)
    top = res.contributors[0]
    share = (top.band.mean / total) if total > 0 else 0.0
    threshold = engine.config.single_acceptance_share

    states = {
        c.exception.id: engine.single_acceptance_state(res.risk.id, c.exception.id)
        for c in res.contributors
    }
    intolerable = [c for c in res.contributors if states.get(c.exception.id) == "over"]
    all_tolerable_alone = not intolerable

    if intolerable:
        return Breach("single-acceptance", share, intolerable[0].exception.id, all_tolerable_alone)
    if share >= threshold:
        return Breach("single-acceptance", share, top.exception.id, all_tolerable_alone)
    return Breach("accumulation", share, None, all_tolerable_alone)


def _exc_label(corpus: Corpus, exc_id: str) -> str:
    exc = next((e for e in corpus.exceptions if e.id == exc_id), None)
    if exc is None:
        return exc_id
    if exc.title:
        return f"{exc_id} ({exc.title})"
    return exc_id


def _risk_section(engine: Engine, corpus: Corpus, res: ResidualResult) -> str:
    risk = res.risk
    badge = APPETITE_BADGE[res.state]
    lines = [f"### {risk.id} — {badge}", ""]

    headline = (
        f"{risk.id} carries **{fmt_band(res.band)}** in residual annual loss exposure against a "
        f"**{fmt_threshold(res.threshold)}** appetite, and {BAND_POSITION[res.state]}."
    )

    if res.state == "within":
        lines.append(headline)
        lines.append("")
        return "\n".join(lines)

    breach = classify_breach(engine, res)
    if breach is not None:
        if breach.kind == "accumulation":
            top_n = min(3, len(res.contributors))
            tol = (
                "each looked tolerable on its own"
                if breach.all_tolerable_alone
                else "no single one dominates"
            )
            headline += (
                f" This is an **accumulation breach**: no single exception caused it — "
                f"the top {top_n} accepted gaps {tol}, and together they breach. "
                f"There is no individual to send this back to; it is a process signal."
            )
        else:
            culprit = _exc_label(corpus, breach.culprit_id) if breach.culprit_id else "one exception"
            headline += (
                f" This is a **single-acceptance breach**: {culprit} accounts for "
                f"{pct(breach.dominant_share)} of the contributed annual loss exposure. "
                f"One owner, one decision to revisit."
            )
    lines.append(headline)
    lines.append("")

    # Attribution: rank the contributing exceptions.
    rows = []
    for c in res.contributors:
        alone = engine.single_acceptance_state(risk.id, c.exception.id)
        rows.append(
            [
                c.exception.id,
                c.exception.title or "—",
                fmt_band(c.band),
                {"over": "yes", "straddling": "maybe", "within": "no"}.get(alone, "—"),
                c.exception.owner or "—",
            ]
        )
    if rows:
        lines.append(
            md_table(
                ["Exception", "What was accepted", "Contribution", "Over alone?", "Owner"],
                rows,
            )
        )
        lines.append("")

    if res.untrusted:
        ids = join_clause([c.exception.id for c in res.untrusted])
        lines.append(
            f"*Not included above (untrusted): {ids}. "
            f"These rest on uncalibrated or vague inputs and are excluded from the band "
            f"until corrected.*"
        )
        lines.append("")

    # Projected residual once the risk's funded remediations land.
    post = engine.post_remediation_residual(risk.id)
    if post is not None and post.applied:
        names = join_clause([r.title or r.id for r in post.applied])
        if post.state == "within":
            verdict = "projected **within** appetite"
        elif post.state == "straddling":
            verdict = "projected to **still straddle** the line"
        else:
            verdict = "projected to **remain over** appetite"
        lines.append(
            f"**After the funded plan** ({names}): {verdict}, at **{fmt_band(post.band)}** "
            f"residual. Conditional on the funded plan executing."
        )
        lines.append("")
    elif post is not None:
        lines.append(
            "*No funded remediation addresses this risk yet, so the projected residual is "
            "unchanged.*"
        )
        lines.append("")
    return "\n".join(lines)


def render_appetite(engine: Engine, corpus: Corpus, config: Config, only_risk: str | None = None) -> str:
    residuals = engine.all_residuals()
    if only_risk:
        residuals = [r for r in residuals if r.risk.id == only_risk]
        if not residuals:
            return f"No computable risk named {only_risk!r}."

    order = {"over": 0, "straddling": 1, "within": 2}
    residuals.sort(key=lambda r: (order[r.state], -r.band.mean))

    out = ["## Appetite breach", ""]

    # Portfolio line: stated tolerance vs revealed carry.
    portfolio = engine.portfolio_residual_band()
    if portfolio is not None and not only_risk:
        stated = engine.portfolio_appetite_total()
        n_over = sum(1 for r in residuals if r.state == "over")
        n_straddle = sum(1 for r in residuals if r.state == "straddling")
        breach_clause = ""
        if n_over or n_straddle:
            parts = []
            if n_over:
                parts.append(f"{plural(n_over, 'risk')} over")
            if n_straddle:
                parts.append(f"{plural(n_straddle, 'risk')} straddling")
            breach_clause = f" {join_clause(parts)} appetite."
        out.append(
            f"Stated tolerance across {plural(len(residuals), 'tracked risk')} sums to "
            f"**{fmt_threshold(stated)}**; the acceptances on the books reveal the organization "
            f"is carrying **{fmt_band(portfolio)}** in residual annual loss exposure.{breach_clause}"
        )
        out.append("")

    breaching = [r for r in residuals if r.state in ("over", "straddling")]
    within = [r for r in residuals if r.state == "within"]

    # Summary: of the risks breaching today, how many remain over after the plan.
    if breaching and not only_risk:
        still_over = [
            r for r in breaching
            if (post := engine.post_remediation_residual(r.risk.id)) is not None and post.state == "over"
        ]
        if still_over:
            names = join_clause([r.risk.id for r in still_over])
            tail = f"{plural(len(still_over), 'risk')} ({names}) {'remains' if len(still_over) == 1 else 'remain'} over"
        else:
            tail = "none remain over"
        out.append(
            f"Of the {plural(len(breaching), 'risk')} over or straddling appetite today, {tail} after "
            f"the funded plan executes. Projections below are conditional on that plan."
        )
        out.append("")

        # Inline chart: one mini-plot per breaching risk, each on its own scale.
        plots = []
        for r in breaching:
            post = engine.post_remediation_residual(r.risk.id)
            plots.append(
                AppetitePlot(
                    name=r.risk.id,
                    current=r.band,
                    current_state=r.state,
                    post=post.band if post is not None else None,
                    post_state=post.state if post is not None else None,
                    appetite=r.threshold,
                )
            )
        out.append(raw_svg_block(appetite_ranges_svg(plots)))
        out.append("")

    if not breaching and not only_risk:
        out.append("All tracked risks are within appetite.")
        out.append("")

    for res in breaching:
        out.append(_risk_section(engine, corpus, res))

    if only_risk:
        for res in within:
            out.append(_risk_section(engine, corpus, res))
    elif within:
        names = join_clause([r.risk.id for r in within])
        out.append(f"**Within appetite:** {names}.")
        out.append("")

    return "\n".join(out).rstrip() + "\n"
