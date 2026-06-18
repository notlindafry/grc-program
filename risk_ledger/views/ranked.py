"""Ranked list -- the action layer.

The artifact handed to a program manager. Defaults to clusters by root cause
(here: the control being deviated from), ranked by expected residual
contribution, with each row carrying a remediation payload so it is assignable as
it stands. The malformed are separated from the actionable: a non-plan
remediation, an uncalibrated estimate, or a reallocation with no destination is
returned for a real assessment instead of ranked as if it were real.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..config import Config
from ..engine import Engine
from ..loader import Corpus
from ..models import Exception_
from ..montecarlo import Band
from ..render import fmt_band, join_clause, md_table, plural, quarter_label


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
    mechanism: str = ""
    target_quarter: str = ""
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
            ids = [m.id for m in members if m.mapped_risk == dominant]
            rb = engine.residual_with(dominant, ids)
            threshold = corpus.risks[dominant].appetite_threshold
            if rb is not None and rb.high > threshold and rb.mean <= threshold:
                cl.tail_risk = True

        # Remediation payload from the clean members.
        cl.mechanism = _modal([m.remediation_mechanism for m in well_formed]) or ""
        targets = [m.remediation_target_date for m in well_formed if m.remediation_target_date]
        cl.target_quarter = quarter_label(max(targets)) if targets else ""
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
    clusters = build_clusters(engine, corpus)

    # "What to fix first" is the action layer: the leverage is in clusters that
    # push a risk over or straddling appetite, plus any whose upper bound alone
    # would breach (the tail-risk catch). Clusters that sit entirely within
    # appetite are real accepted risk but not urgent; they surface in the drift
    # view (they are largely the migration's external footprint), not here.
    fix_first = [c for c in clusters if c.breaches or c.tail_risk]
    within_only = [c for c in clusters if not (c.breaches or c.tail_risk)]

    out = ["## Ranked list — what to fix first", ""]
    out.append(
        "Grouped by root cause (the control deviated from), ranked by expected residual "
        "contribution. Each row is ready to assign. Only clusters that breach an appetite — or "
        "whose upper bound alone would — are listed; clusters that sit within appetite appear in "
        "the drift view, not here."
    )
    out.append("")

    rows = []
    for i, c in enumerate(fix_first, start=1):
        notes = []
        if c.action_flagged:
            notes.append(f"{len(c.action_flagged)} of {len(c.members)} malformed, re-assess first")
        if c.tail_risk:
            notes.append("upper bound alone breaches appetite (tail risk)")
        if not notes:
            notes.append("well-formed")
        remediation = (
            f"{c.mechanism}, target {c.target_quarter}"
            if c.mechanism and c.target_quarter
            else (c.mechanism or "—")
        )
        rows.append(
            [
                str(i),
                c.label,
                fmt_band(c.band),
                join_clause(c.breaches) or "—",
                remediation,
                c.owner,
                "; ".join(notes),
            ]
        )
    if rows:
        out.append(
            md_table(
                ["Rank", "Cluster / exception", "Expected residual", "Breaches", "Remediation", "Owner", "Notes"],
                rows,
            )
        )
        out.append("")
    else:
        out.append("No cluster currently breaches an appetite. Real accepted risk remains; see the drift view.")
        out.append("")

    if within_only:
        out.append(
            f"*{plural(len(within_only), 'further cluster')} contribute to risks that remain within "
            f"appetite and {'is' if len(within_only) == 1 else 'are'} not ranked here.*"
        )
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
