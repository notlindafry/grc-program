"""Drift view -- the per-OKR lens.

Turns a pile of individually-approved exceptions into the one sentence that shows
an OKR betraying its stated intent. An OKR has two distinct risk footprints and
the view keeps them separate:

* **Internal** -- exceptions filed *against* the OKR (``okr == X``), accepting
  debt to hit its deadline. These degrade the OKR's own risks: the quality
  rebuild becoming a lift-and-shift.
* **External** -- exceptions filed against *other* OKRs that name this one in
  ``diverted_to``. Their security work did not happen because their people were
  pulled here. This footprint is invisible on the OKR's own ledger and surfaces
  only when you read the whole corpus.

An OKR is an Objective plus Key Results; the view displays the key results as the
commitments the exception footprint is eroding.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass

from ..config import Config
from ..engine import Engine
from ..loader import Corpus
from ..models import Exception_
from ..montecarlo import Band
from ..render import EN_DASH, fmt_band, join_clause, md_table, plural, raw_svg_block
from ..render_svg import drift_ledgers_svg


@dataclass
class Footprint:
    okr: str
    internal: list[Exception_]
    external: list[Exception_]
    internal_band: Band | None
    external_band: Band | None
    combined_band: Band | None
    external_by_project: dict[str, tuple[int, Band | None]]
    all_filed: list[Exception_]  # for trajectory (any status)


def _band_or_dash(band: Band | None) -> str:
    return fmt_band(band) if band is not None else "—"


def build_footprint(engine: Engine, corpus: Corpus, okr: str) -> Footprint:
    internal = [
        e for e in corpus.exceptions
        if e.okr == okr and e.is_active and e.counts_in_bands
    ]
    external = [
        e for e in corpus.exceptions
        if e.diverted_to == okr and e.is_active and e.counts_in_bands
    ]
    by_project_ids: dict[str, list[str]] = defaultdict(list)
    for e in external:
        by_project_ids[e.okr].append(e.id)
    external_by_project = {
        proj: (len(ids), engine.combined_band(ids)) for proj, ids in by_project_ids.items()
    }
    all_filed = [
        e for e in corpus.exceptions
        if e.okr == okr or e.diverted_to == okr
    ]
    return Footprint(
        okr=okr,
        internal=internal,
        external=external,
        internal_band=engine.combined_band([e.id for e in internal]),
        external_band=engine.combined_band([e.id for e in external]),
        combined_band=engine.combined_band([e.id for e in internal + external]),
        external_by_project=external_by_project,
        all_filed=all_filed,
    )


@dataclass
class Trajectory:
    earliest: dt.date
    latest: dt.date
    end: dt.date
    first_quarter_count: int
    final_stretch_count: int
    final_stretch_weeks: int
    monthly: list[tuple[str, int]]
    accelerating: bool


def build_trajectory(footprint: Footprint, config: Config, period_end: dt.date | None) -> Trajectory | None:
    dated = sorted([e for e in footprint.all_filed if e.filed_on], key=lambda e: e.filed_on)
    if not dated:
        return None
    earliest = dated[0].filed_on
    latest = dated[-1].filed_on
    end = period_end or latest
    stretch = dt.timedelta(weeks=config.final_stretch_weeks)
    final_start = end - stretch
    first_quarter_end = earliest + dt.timedelta(days=91)

    first_quarter_count = sum(1 for e in dated if earliest <= e.filed_on <= first_quarter_end)
    final_stretch_count = sum(1 for e in dated if final_start < e.filed_on <= end)

    months: Counter = Counter()
    for e in dated:
        months[(e.filed_on.year, e.filed_on.month)] += 1
    monthly = [(f"{y}-{m:02d}", n) for (y, m), n in sorted(months.items())]

    # Acceleration tell: final-stretch filing rate well above the average rate.
    span_weeks = max((latest - earliest).days / 7.0, 1.0)
    avg_per_week = len(dated) / span_weeks
    final_rate = final_stretch_count / max(config.final_stretch_weeks, 1)
    accelerating = final_rate > 1.5 * avg_per_week and final_stretch_count >= 3

    return Trajectory(
        earliest=earliest,
        latest=latest,
        end=end,
        first_quarter_count=first_quarter_count,
        final_stretch_count=final_stretch_count,
        final_stretch_weeks=config.final_stretch_weeks,
        monthly=monthly,
        accelerating=accelerating,
    )


def _okr_section(engine: Engine, corpus: Corpus, config: Config, okr: str) -> str:
    fp = build_footprint(engine, corpus, okr)
    meta = corpus.okrs.get(okr)
    objective = meta.objective if meta and meta.objective else None
    key_results = meta.key_results if meta else []
    period_end = meta.period_end if meta else None
    traj = build_trajectory(fp, config, period_end)

    title = meta.title if meta else okr
    lines = [f"### {title}", ""]

    # Headline sentence -- the thing a busy executive cannot unsee.
    obj_clause = (
        f"objective: {objective}."
        if objective
        else "(no objective registered in okrs.yaml)."
    )
    parts = [f"**{okr}** — {obj_clause}"]

    if fp.internal:
        parts.append(
            f"On itself, {plural(len(fp.internal), 'exception')} accept debt or defer "
            f"hardening to hit the deadline, adding {_band_or_dash(fp.internal_band)} to its own risks."
        )
    if fp.external:
        breakdown = join_clause(
            [f"{proj} ({cnt})" for proj, (cnt, _) in sorted(
                fp.external_by_project.items(), key=lambda kv: -kv[1][0])]
        )
        parts.append(
            f"On other OKRs, {plural(len(fp.external), 'exception')} name {okr} "
            f"as where their resources went, adding {_band_or_dash(fp.external_band)} to those "
            f"OKRs' risks ({breakdown})."
        )
    if traj and (traj.first_quarter_count or traj.final_stretch_count):
        parts.append(
            f"Acceptance went from {traj.first_quarter_count} in the first quarter to "
            f"{traj.final_stretch_count} in the final {traj.final_stretch_weeks} weeks"
            + (" — accelerating sharply into the deadline." if traj.accelerating else ".")
        )
    if fp.external and len(fp.external_by_project) >= 1:
        commitments = "these key results" if key_results else "its own quality"
        parts.append(
            f"The work traded {commitments} for the date and pulled "
            f"{plural(len(fp.external_by_project), 'other team')}' capacity to do it."
        )
    lines.append(" ".join(parts))
    lines.append("")

    # Key results: the commitments the footprint above is eroding.
    if key_results:
        lines.append("**Key results at stake:**")
        for kr in key_results:
            lines.append(f"- {kr}")
        lines.append("")

    # Footprint table.
    rows = [
        ["Internal (on itself)", str(len(fp.internal)), _band_or_dash(fp.internal_band)],
        ["External (on starved OKRs)", str(len(fp.external)), _band_or_dash(fp.external_band)],
        ["**Combined**", str(len(fp.internal) + len(fp.external)), _band_or_dash(fp.combined_band)],
    ]
    lines.append(md_table(["Footprint", "Exceptions", "Added residual risk"], rows))
    lines.append("")

    # Two-ledger chart: the on-ledger (internal) footprint vs the true
    # (internal + external) footprint. Only when both footprints exist, so the
    # reported-vs-true contrast is meaningful; the prose above states both bands.
    if fp.internal_band is not None and fp.external_band is not None:
        lines.append(raw_svg_block(drift_ledgers_svg(okr, fp.internal_band, fp.combined_band)))
        lines.append("")

    if fp.external_by_project:
        ext_rows = [
            [proj, str(cnt), _band_or_dash(band)]
            for proj, (cnt, band) in sorted(fp.external_by_project.items(), key=lambda kv: -kv[1][0])
        ]
        lines.append("**External footprint by starved OKR**")
        lines.append("")
        lines.append(md_table(["OKR (filer)", "Exceptions", "Added residual risk"], ext_rows))
        lines.append("")

    if traj:
        lines.append(
            f"**Trajectory** ({traj.earliest.isoformat()} {EN_DASH} {traj.latest.isoformat()})"
        )
        lines.append("")
        traj_rows = []
        prev = None
        for label, n in traj.monthly:
            if prev is None:
                change = "—"  # first row has no previous month
            else:
                change = f"{round((n - prev) / prev * 100):+d}%"
            traj_rows.append([label, str(n), change])
            prev = n
        lines.append(md_table(["Month", "Exceptions filed", "Month Over Month Change"], traj_rows))
        lines.append("")

    return "\n".join(lines)


def render_drift(
    engine: Engine,
    corpus: Corpus,
    config: Config,
    only_okr: str | None = None,
    significant_only: bool = False,
) -> str:
    # Every OKR that is either filed-against or diverted-to.
    names: set[str] = set()
    diverted_targets: set[str] = set()
    for e in corpus.exceptions:
        if e.okr:
            names.add(e.okr)
        if e.diverted_to:
            names.add(e.diverted_to)
            diverted_targets.add(e.diverted_to)

    if only_okr:
        if only_okr not in names and only_okr not in corpus.okrs:
            return f"No OKR named {only_okr!r} appears in the corpus."
        targets = [only_okr]
    else:
        candidates = names
        if significant_only:
            # The drift-specific signal is the external footprint: an OKR that
            # pulled resources from others. An OKR with only its own accepted debt
            # is already covered, per risk, by the appetite view.
            candidates = {n for n in names if n in diverted_targets}
        scored = []
        for name in candidates:
            fp = build_footprint(engine, corpus, name)
            mean = fp.combined_band.mean if fp.combined_band else 0.0
            scored.append((mean, name))
        targets = [name for _, name in sorted(scored, key=lambda s: -s[0])]

    out = ["## Drift", ""]
    if not only_okr:
        out.append(
            "Each OKR has two footprints: the risk it accepts on itself, and the risk it pushes "
            "onto the OKRs it pulled resources from. The second is invisible on its own ledger."
        )
        out.append("")
    if not targets:
        out.append("No OKR shows an external footprint.")
        out.append("")
    for name in targets:
        out.append(_okr_section(engine, corpus, config, name))
    return "\n".join(out).rstrip() + "\n"
