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
from .views.appetite import classify_breach, render_appetite
from .views.drift import build_footprint, render_drift
from .views.ranked import fix_first_clusters, render_ranked


def _top_line(engine: Engine, corpus: Corpus, config: Config) -> str:
    # Dominant OKR by combined footprint.
    names: set[str] = set()
    for e in corpus.exceptions:
        if e.okr:
            names.add(e.okr)
        if e.diverted_to:
            names.add(e.diverted_to)
    dominant = None
    best = 0.0
    for name in names:
        fp = build_footprint(engine, corpus, name)
        mean = fp.combined_band.mean if fp.combined_band else 0.0
        if mean > best:
            best, dominant = mean, name

    residuals = engine.all_residuals()
    breaching = [r for r in residuals if r.state in ("over", "straddling")]
    accumulation = 0
    for r in breaching:
        b = classify_breach(engine, r)
        if b and b.kind == "accumulation":
            accumulation += 1

    clusters = fix_first_clusters(engine, corpus)
    top_cluster = clusters[0] if clusters else None

    parts = []
    if dominant:
        parts.append(
            f"the **{dominant}** OKR is the dominant source of newly accepted risk"
        )
    if breaching:
        parts.append(f"**{plural(len(breaching), 'risk')} now carry residual exposure above appetite**")
    else:
        parts.append("all tracked risks remain within appetite")
    sentence = "Across the active exception corpus, " + join_clause(parts) + "."

    if breaching and accumulation >= max(1, len(breaching) - accumulation):
        sentence += " Most of that breach comes from accumulation rather than any single decision."
    if top_cluster is not None:
        sentence += f" Fixing the {top_cluster.label} would clear the largest single share of it."
    return sentence


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
        "# Exception Risk Report",
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
        render_drift(engine, corpus, config, significant_only=True),
        "---",
        "",
        render_appetite(engine, corpus, config),
        "---",
        "",
        render_ranked(engine, corpus, config),
        "---",
        "",
        _data_confidence(engine, corpus, config),
    ]
    return "\n".join(out).rstrip() + "\n"
