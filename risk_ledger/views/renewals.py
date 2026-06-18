"""Persistence view -- the renewals lens.

A temporary exception renewed unchanged is the death-by-a-thousand-cuts pattern
in time: the acceptance keeps coming back without anyone revisiting whether it
still holds, and "temporary" quietly becomes the rule. This view finds the active
exceptions renewed at or past the alert threshold whose justification was never
revisited, and the residual exposure they carry.
"""

from __future__ import annotations

from ..config import Config
from ..engine import Engine
from ..loader import Corpus
from ..models import Exception_
from ..render import fmt_band, md_table, plural


def _short_risk(rid: str) -> str:
    return rid[len("RISK-"):] if rid.startswith("RISK-") else rid


def flagged_renewals(corpus: Corpus, config: Config) -> list[Exception_]:
    """The 'temporary forever' set, sorted by renewal_count descending.

    Active exceptions renewed at least ``config.renewal_alert_count`` times whose
    justification has never changed (``justification_changed_last is None``).
    """
    flagged = [
        e
        for e in corpus.exceptions
        if e.is_active
        and e.renewal_count >= config.renewal_alert_count
        and e.justification_changed_last is None
    ]
    flagged.sort(key=lambda e: e.renewal_count, reverse=True)
    return flagged


def render_renewals(engine: Engine, corpus: Corpus, config: Config) -> str:
    flagged = flagged_renewals(corpus, config)
    renewed_once = sum(1 for e in corpus.exceptions if e.is_active and e.renewal_count >= 1)
    band = engine.combined_band([e.id for e in flagged if e.counts_in_bands])

    out = ["## Persistence", ""]
    out.append(
        "A temporary exception renewed unchanged is the rule in disguise: the acceptance keeps "
        "coming back without anyone revisiting whether it still holds."
    )
    out.append("")

    exposure = (
        f", carrying **{fmt_band(band)}** in residual annual loss exposure" if band is not None else ""
    )
    out.append(
        f"{renewed_once} active "
        f"{'exception has' if renewed_once == 1 else 'exceptions have'} been renewed at least once; "
        f"**{len(flagged)} {'has' if len(flagged) == 1 else 'have'} been renewed "
        f"{config.renewal_alert_count} or more times with the justification never revisited**"
        f"{exposure}. That is 'temporary' becoming permanent."
    )
    out.append("")

    if flagged:
        rows = [
            [
                e.id,
                e.title or "—",
                str(e.renewal_count),
                _short_risk(e.mapped_risk),
                e.owner or "—",
            ]
            for e in flagged
        ]
        out.append(
            md_table(["Exception", "What was accepted", "Renewals", "Mapped risk", "Owner"], rows)
        )
        out.append("")
    else:
        out.append(f"No active exception has been renewed {plural(config.renewal_alert_count, 'time')} unchanged.")
        out.append("")

    return "\n".join(out).rstrip() + "\n"
