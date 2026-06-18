"""Ranked list -- the action layer.

The artifact handed to a program manager. Defaults to clusters by root cause
(here: the control being deviated from), ranked by expected residual
contribution, with each row carrying a remediation payload so it is assignable as
it stands. The malformed are separated from the actionable: a non-plan
remediation, an uncalibrated estimate, or a reallocation with no destination is
returned for a real assessment instead of ranked as if it were real.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..config import Config
from ..engine import Engine
from ..loader import Corpus
from ..models import Exception_
from ..montecarlo import Band
from ..render import fmt_band, join_clause, md_table, plural


def _modal(values: list[str]) -> str | None:
    vals = [v for v in values if v]
    if not vals:
        return None
    return Counter(vals).most_common(1)[0][0]


def _short_risk(rid: str) -> str:
    return rid[len("RISK-"):] if rid.startswith("RISK-") else rid


@dataclass
class Cluster:
    control: str
    members: list[Exception_]
    well_formed: list[Exception_]
    action_flagged: list[Exception_]
    band: Band | None = None
    breaches: list[str] = field(default_factory=list)
    tail_risk: bool = False
    dominant_risk: str = ""
    mechanism: str = ""
    reduces: str = ""
    deadline: dt.date | None = None
    owner: str = ""

    @property
    def is_rankable(self) -> bool:
        # Needs at least one clean member to carry a remediation payload.
        return bool(self.well_formed) and self.band is not None

    @property
    def label(self) -> str:
        if len(self.members) == 1:
            e = self.members[0]
            return f"{e.id} — {e.title}" if e.title else e.id
        ctrl = self.control or "(no control)"
        return f"{ctrl} (cluster, {plural(len(self.members), 'exception')})"

    @property
    def action_to_take(self) -> str:
        """Narrative remediation built from the cluster's well-formed members:
        modal mechanism, modal reduces, and the latest member deadline."""
        if not self.mechanism:
            return "—"
        when = self.deadline.isoformat() if self.deadline else "—"
        text = (
            f"{self.mechanism} in order to reduce {self.reduces} no later than {when}"
        ).replace("_", " ")
        return text[:1].upper() + text[1:]


def build_clusters(engine: Engine, corpus: Corpus) -> list[Cluster]:
    trusted_active = [e for e in corpus.exceptions if e.is_active and e.counts_in_bands]
    groups: dict[str, list[Exception_]] = defaultdict(list)
    for e in trusted_active:
        groups[e.control or "(no control)"].append(e)

    clusters: list[Cluster] = []
    for control, members in groups.items():
        well_formed = [m for m in members if m.is_well_formed]
        action_flagged = [m for m in members if m.action_flags]
        cl = Cluster(
            control=control,
            members=members,
            well_formed=well_formed,
            action_flagged=action_flagged,
            band=engine.combined_band([m.id for m in members]),
        )

        # Which over/straddling risks does this cluster feed?
        risk_means: dict[str, float] = defaultdict(float)
        for m in members:
            b = engine.contribution_band(m.id)
            if b:
                risk_means[m.mapped_risk] += b.mean
        breaches = []
        for rid in risk_means:
            res = engine.residual(rid)
            if res and res.state in ("over", "straddling"):
                breaches.append(_short_risk(rid))
        cl.breaches = sorted(set(breaches))

        # Tail-risk catch on the cluster's dominant risk.
        if risk_means:
            dominant = max(risk_means, key=risk_means.get)
            cl.dominant_risk = dominant
            ids = [m.id for m in members if m.mapped_risk == dominant]
            rb = engine.residual_with(dominant, ids)
            threshold = corpus.risks[dominant].appetite_threshold
            if rb is not None and rb.high > threshold and rb.mean <= threshold:
                cl.tail_risk = True

        # Remediation payload from the clean members.
        cl.mechanism = _modal([m.remediation_mechanism for m in well_formed]) or ""
        cl.reduces = _modal([m.remediation_reduces for m in well_formed]) or ""
        expiries = [m.expires_on for m in well_formed if m.expires_on]
        cl.deadline = max(expiries) if expiries else None
        cl.owner = _modal([m.owner for m in well_formed]) or "—"
        clusters.append(cl)

    rankable = [c for c in clusters if c.is_rankable]
    rankable.sort(key=lambda c: c.band.mean, reverse=True)
    return rankable


def fix_first_clusters(engine: Engine, corpus: Corpus) -> list[Cluster]:
    """Rankable clusters that breach an appetite or whose upper bound alone would.

    This is the "what to fix first" set: where the leverage is. Shared by the
    ranked view and the report's top line so they cannot disagree.
    """
    return [c for c in build_clusters(engine, corpus) if c.breaches or c.tail_risk]


# ---------------------------------------------------------------------------
# Unified ranking -- remediations and unfunded clusters together, by risk
# reduction (the dollars an action buys down).
# ---------------------------------------------------------------------------


@dataclass
class RankItem:
    label: str
    reduction: Band
    breaches: str   # rendered Breaches cell
    action: str
    owner: str
    kind: str       # "remediation" | "cluster"
    source_id: str  # remediation id or control


def _remediation_breaches(engine: Engine, corpus: Corpus, rem) -> list[str]:
    """Over/straddling risks this remediation addresses (short form)."""
    if rem.type == "restore":
        risks = {
            e.mapped_risk
            for e in corpus.exceptions
            if e.is_active and e.counts_in_bands and e.control == rem.restores_control
        }
    else:
        risks = {rem.mapped_risk}
    out = []
    for rid in risks:
        res = engine.residual(rid)
        if res and res.state in ("over", "straddling"):
            out.append(_short_risk(rid))
    return sorted(out)


def _remediation_reduces(corpus: Corpus, rem) -> str:
    if rem.type == "strengthen":
        return rem.moves or "residual risk"
    # restore: the factor the cleared exceptions were degrading
    return _modal(
        [
            e.remediation_reduces
            for e in corpus.exceptions
            if e.is_active and e.control == rem.restores_control
        ]
    ) or "residual risk"


def _remediation_action(corpus: Corpus, rem) -> str:
    if not rem.mechanism:
        return "—"
    when = rem.target_date.isoformat() if rem.target_date else "—"
    text = (
        f"{rem.mechanism} in order to reduce {_remediation_reduces(corpus, rem)} no later than {when}"
    ).replace("_", " ")
    return text[:1].upper() + text[1:]


def _cluster_breaches_cell(c: Cluster) -> str:
    if c.breaches:
        return join_clause(c.breaches)
    if c.tail_risk and c.dominant_risk:
        return f"{_short_risk(c.dominant_risk)} (tail)"
    return "—"


def unified_ranking(engine: Engine, corpus: Corpus) -> list[RankItem]:
    """Funded remediations and unfunded breaching clusters, ranked by the risk
    reduction each buys down. A cluster a funded restore covers is represented by
    the remediation row, not separately."""
    items: list[RankItem] = []
    funded = engine.funded_remediations()
    funded_restored = {r.restores_control for r in funded if r.type == "restore" and r.restores_control}

    for rem in funded:
        reduction = engine.risk_reduction(rem)
        if reduction is None:
            continue
        items.append(
            RankItem(
                label=f"{rem.id} — {rem.title}" if rem.title else rem.id,
                reduction=reduction,
                breaches=join_clause(_remediation_breaches(engine, corpus, rem)) or "—",
                action=_remediation_action(corpus, rem),
                owner=rem.owner or "—",
                kind="remediation",
                source_id=rem.id,
            )
        )

    for c in fix_first_clusters(engine, corpus):
        if c.control in funded_restored:
            continue  # dedup: a funded restore already represents this cluster
        items.append(
            RankItem(
                label=c.label,
                reduction=c.band,
                breaches=_cluster_breaches_cell(c),
                action=c.action_to_take,
                owner=c.owner,
                kind="cluster",
                source_id=c.control,
            )
        )

    items.sort(key=lambda it: it.reduction.mean, reverse=True)
    return items


# Send-back buckets, in the order we present them.
_SEND_BACK_BUCKETS = [
    ("non_plan", "Non-plan remediation", "no target date and/or mechanism — returned for a real plan"),
    (
        "reallocation",
        "Reallocation with no destination",
        "reason is resource_reallocation with no diverted_to — returned to state where the resources went",
    ),
    (
        "estimate",
        "Uncalibrated or stale estimate",
        "estimate not from a calibrated, in-window estimator — returned for re-estimation",
    ),
    ("scope", "Scope not explicit", "scope is vague or undefined — returned to enumerate the assets"),
    ("reason", "Unrecognized reason", "reason is not a recognized category — returned to re-file"),
]


def _bucket_for(code: str) -> str:
    if code == "remediation_non_plan":
        return "non_plan"
    if code == "reallocation_no_destination":
        return "reallocation"
    if code.startswith("estimator_"):
        return "estimate"
    if code.startswith("scope"):
        return "scope"
    if code == "reason_unknown":
        return "reason"
    return "other"


def render_ranked(engine: Engine, corpus: Corpus, config: Config) -> str:
    items = unified_ranking(engine, corpus)

    out = ["## What to fix first", ""]
    out.append(
        "This ranks the work that moves quantified risk, by the residual it buys down, whether the "
        "lever is clearing an accepted exception or executing a funded remediation. A risk with no "
        "exception and no funded plan does not appear; a risk over appetite with no acceptance "
        "behind it is a control-sufficiency problem this view surfaces but does not remediate by "
        "clearing an exception."
    )
    out.append("")

    rows = [
        [str(i), it.label, fmt_band(it.reduction), it.breaches, it.action, it.owner]
        for i, it in enumerate(items, start=1)
    ]
    if rows:
        out.append(
            md_table(
                ["Rank", "Item", "Risk reduction", "Breaches", "Action to take", "Owner"],
                rows,
            )
        )
        out.append("")
    else:
        out.append("No funded remediation and no breaching exception cluster.")
        out.append("")

    # Send-back bucket.
    flagged = [e for e in corpus.exceptions if e.is_active and e.send_back]
    bucket_members: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for e in flagged:
        for issue in e.flags:
            bucket_members[_bucket_for(issue.code)][e.id].append(issue.message)

    if flagged:
        out.append("### Sent back, not ranked")
        out.append("")
        out.append(
            "A theatrical exception cannot be actioned. These are returned for a real assessment "
            "before they can be assigned."
        )
        out.append("")
        for key, title, gloss in _SEND_BACK_BUCKETS:
            members = bucket_members.get(key)
            if not members:
                continue
            ids = join_clause(sorted(members.keys()))
            out.append(f"- **{title}** ({ids}) — {gloss}.")
        out.append("")

    # Rejected (hard errors) are not actionable at all; point to `validate`.
    rejected = [e for e in corpus.exceptions if e.rejected]
    if rejected:
        ids = join_clause(sorted(e.id or e.path for e in rejected))
        out.append(
            f"*{plural(len(rejected), 'record')} rejected outright (hard validation error): {ids}. "
            f"Run `risk-ledger validate` for details.*"
        )
        out.append("")

    return "\n".join(out).rstrip() + "\n"
