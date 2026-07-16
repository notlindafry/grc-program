"""Graph-backed views ported from the retired legacy v1 (SPEC v2.2 §C1, §C2).

Two capabilities survive the legacy retirement because they drive dashboard
views the ecosystem engine did not already cover:

* **Renewals / can-kicking** (view 5) -- "temporary forever" exceptions renewed
  past the alert count without their justification ever being revisited, plus
  remediations whose target date has already slipped.
* **Drift** (view 4) -- the per-OKR two-ledger read: an OKR's *reported* risk
  footprint (the exceptions filed on it) versus its *true* footprint once the
  ``diverted_to`` resource reallocation from other OKRs is counted. The most
  distinctive capability in the tool; the ``diverted_to`` data already lives on
  the v2 issues, so the port is mechanical.

Both run on the assembled :class:`Graph` and the :class:`GraphEngine`; nothing
here re-implements the quant -- drift reuses the engine's per-issue contribution
samples, and renewals is pure record inspection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import Config
from .graph import Graph
from .graph_engine import GraphEngine
from .models import IssueRecord
from .montecarlo import Band
from .render import EN_DASH, fmt_band, fmt_money


# ---------------------------------------------------------------------------
# Renewals / can-kicking (view 5)
# ---------------------------------------------------------------------------


def flagged_renewals(graph: Graph, config: Config) -> list[IssueRecord]:
    """Active exceptions renewed >= the alert count with the justification never
    revisited -- a temporary acceptance that has quietly become the rule."""
    out = [
        i for i in graph.issues
        if i.type == "exception" and i.is_active
        and i.renewal_count >= config.renewal_alert_count
        and not i.justification_changed_last
    ]
    out.sort(key=lambda i: i.renewal_count, reverse=True)
    return out


def slipped_remediations(graph: Graph, config: Config) -> list:
    """Remediations whose target date is already in the past and are not yet
    complete (funded/in_progress/proposed all still 'open') -- chronic deferral."""
    out = [
        r for r in graph.remediations
        if r.target_date is not None and r.target_date < config.as_of
    ]
    out.sort(key=lambda r: r.target_date)
    return out


def render_renewals(graph: Graph, config: Config) -> str:
    lines = ["# The can you keep kicking\n"]
    renewed = flagged_renewals(graph, config)
    lines.append(f"## Temporary-forever exceptions ({len(renewed)})\n")
    if renewed:
        lines.append("Renewed at least "
                     f"{config.renewal_alert_count}x without the justification being revisited.\n")
        for e in renewed:
            lines.append(f"- {e.id} — renewed {e.renewal_count}x — {e.title}")
    else:
        lines.append("_None._")
    slipped = slipped_remediations(graph, config)
    lines.append(f"\n## Remediations with slipped target dates ({len(slipped)})\n")
    for r in slipped[:20]:
        lines.append(f"- {r.id} [{r.status}] target {r.target_date} — {r.title}")
    if len(slipped) > 20:
        lines.append(f"- …and {len(slipped) - 20} more")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Drift -- the per-OKR two-ledger view (view 4)
# ---------------------------------------------------------------------------


@dataclass
class Drift:
    okr: str
    reported: Optional[Band]       # exposure the OKR's own ledger shows
    true: Optional[Band]           # reported + risk debt diverted INTO it
    reported_ids: list[str] = field(default_factory=list)
    diverted_in_ids: list[str] = field(default_factory=list)

    @property
    def has_undeclared_debt(self) -> bool:
        return bool(self.diverted_in_ids)


def build_drift(graph: Graph, engine: GraphEngine, okr: str) -> Drift:
    """The two ledgers for one OKR (SPEC v2.2 §C2).

    * *reported* — the factor-moving exceptions filed on this OKR (``issue.okr``).
    * *true* — reported plus the exceptions filed on *other* OKRs whose resources
      were reallocated here (``reason_detail.diverted_to == okr``), so this OKR
      truly carries their deferred risk debt even though its own ledger hides it.
    """
    reported_ids = [
        i.id for i in graph.issues
        if i.okr == okr and engine.has_contribution(i.id)
    ]
    diverted_in_ids = [
        i.id for i in graph.issues
        if i.diverted_to == okr and i.okr != okr and engine.has_contribution(i.id)
    ]
    reported = engine.combined_contribution_band(reported_ids)
    true = engine.combined_contribution_band(reported_ids + diverted_in_ids)
    return Drift(okr, reported, true, reported_ids, diverted_in_ids)


def all_drift(graph: Graph, engine: GraphEngine) -> list[Drift]:
    out = [build_drift(graph, engine, okr) for okr in graph.okrs]
    # Most undeclared debt first (largest gap between true and reported means).
    def gap(d: Drift) -> float:
        t = d.true.mean if d.true else 0.0
        r = d.reported.mean if d.reported else 0.0
        return t - r
    out.sort(key=gap, reverse=True)
    return out


def _band_or_dash(b: Optional[Band]) -> str:
    return fmt_band(b) if b else EN_DASH


def render_drift(graph: Graph, engine: GraphEngine, config: Config, only_okr: str | None = None) -> str:
    lines = ["# Drift — reported vs. true OKR footprint\n"]
    lines.append("Each OKR's own ledger shows the risk it accepted directly. Its *true* "
                 "footprint adds the risk debt from other OKRs whose work was deferred to "
                 "fund it (`diverted_to`). The gap is undeclared risk debt.\n")
    drifts = all_drift(graph, engine)
    if only_okr:
        drifts = [d for d in drifts if d.okr == only_okr]
    for d in drifts:
        if not d.reported and not d.true:
            continue
        okr = graph.okrs.get(d.okr)
        title = okr.objective if okr and okr.objective else d.okr
        lines.append(f"## {d.okr} — {title}\n")
        lines.append(f"- Reported footprint: {_band_or_dash(d.reported)}")
        lines.append(f"- True footprint:     {_band_or_dash(d.true)}")
        if d.has_undeclared_debt:
            gap = (d.true.mean if d.true else 0) - (d.reported.mean if d.reported else 0)
            lines.append(f"- Undeclared debt from {len(d.diverted_in_ids)} reallocated "
                         f"exception(s): ~{fmt_money(gap)} of carried exposure the ledger hides.")
        lines.append("")
    return "\n".join(lines)
