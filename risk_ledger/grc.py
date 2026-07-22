"""The GRC-program derivation layer (v4.0 Spec 1 §1.A–§1.C).

This module serves the GRC tab: the health of the program itself — coverage,
hygiene, throughput, and the governance of AI — for a GRC Manager. It is NOT
the eng view: the residual number belongs to the eng tab and does not lead
here. Every derivation below is a **diagnostic**; none moves residual (the
one-path rule, SPEC §4, holds — the only factor-moving issue type is
``exception``, and the deviation overlay in §1.C is provisional, bounded, and
never added to the eng portfolio).

Isolation (P.4): the eng build path is not called through here and is
unchanged. This module loads the same corpus via :func:`load_graph`, then
*additionally* reads the v4.0 registers the eng loader never opens —
``regulations.yaml``, ``sla_config.yaml``, ``guardrails.yaml``,
``agent_inventory.yaml``, and ``guardrail_events/`` (never ``issues/``).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .config import Config
from .graph import Graph
from .graph_engine import RAG_BELOW, GraphEngine
from .loader import load_graph
from .models import ISSUE_FINDING, Issue, IssueRecord, _as_date, _ci, _str_list
from .montecarlo import (
    LOSS_MAGNITUDE,
    OPPORTUNITY_FREQUENCY,
    PROBABILITY_OF_REALIZATION,
    Band,
    MonteCarlo,
    fit_distribution,
)
from .validation import validate_graph

# ---------------------------------------------------------------------------
# v4.0 register records (§0.B–§0.E). Parsed defensively, like everything else.
# ---------------------------------------------------------------------------

# Review cadence -> allowed age in days before a review is overdue. Mirrors the
# evidence cadence windows; ``annual`` is the sla_config default (12 months).
_CADENCE_DAYS = {"monthly": 31, "quarterly": 92, "semiannual": 184, "annual": 366}

# The four rungs a complete response ladder declares (§0.D).
LADDER_RUNGS = ("low", "medium", "high", "critical")

# Dispositions that contribute to the provisional overlay (§1.C): a proposed
# deviation awaits ratification, an accepted one is ratified; dismissed and
# remediated contribute nothing.
CONTRIBUTING_DISPOSITIONS = ("proposed", "accepted")
DISPOSITIONS = ("proposed", "dismissed", "accepted", "remediated")


@dataclass
class Requirement:
    """One external obligation (§0.B): framework + requirement, satisfied by
    existing ISO controls (map once, satisfy many)."""

    id: str
    framework: str
    requirement_ref: str
    title: str
    satisfied_by_controls: list[str]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, rid: str, raw: dict[str, Any]) -> "Requirement":
        return cls(
            id=rid,
            framework=str(raw.get("framework", "")),
            requirement_ref=str(raw.get("requirement_ref", "")),
            title=str(raw.get("title", rid)),
            satisfied_by_controls=_str_list(raw.get("satisfied_by_controls")),
            raw=raw,
        )


@dataclass
class SLAConfig:
    """Authored service-level targets (§0.C) — commitments, never derived."""

    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "SLAConfig":
        return cls(raw=raw or {})

    def _int(self, key: str, default: int) -> int:
        try:
            return int(self.raw.get(key, default))
        except (TypeError, ValueError):
            return default

    @property
    def policy_review_cadence_months(self) -> int:
        return self._int("policy_review_cadence_months", 12)

    @property
    def exception_raised_to_decided_days(self) -> int:
        return self._int("exception_raised_to_decided_days", 5)

    @property
    def finding_to_remediation_plan_days(self) -> int:
        return self._int("finding_to_remediation_plan_days", 15)


@dataclass
class Guardrail:
    """A declared agent guardrail (§0.D): policy-as-code for agents, traced up
    to a governing policy and mapped to the named risk its violation moves."""

    id: str
    title: str
    layer: str
    assertion: str
    policy: str
    mapped_named_risks: list[str]
    applies_to: list[str]
    autonomy_tier: Optional[int]
    owner: str
    rmf_functions: list[str]
    monitoring: dict[str, Any] = field(default_factory=dict)
    provisional_move: dict[str, Any] = field(default_factory=dict)
    response_ladder: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, gid: str, raw: dict[str, Any]) -> "Guardrail":
        tier = raw.get("autonomy_tier")
        monitoring = raw.get("monitoring") if isinstance(raw.get("monitoring"), dict) else {}
        move = raw.get("provisional_move") if isinstance(raw.get("provisional_move"), dict) else {}
        ladder_raw = raw.get("response_ladder") if isinstance(raw.get("response_ladder"), dict) else {}
        return cls(
            id=gid,
            title=str(raw.get("title", gid)),
            layer=str(raw.get("layer", "")),
            assertion=str(raw.get("assertion", "")),
            policy=str(raw.get("policy", "")),
            mapped_named_risks=_str_list(raw.get("mapped_named_risks")),
            applies_to=_str_list(raw.get("applies_to")),
            autonomy_tier=int(tier) if isinstance(tier, int) else None,
            owner=str(raw.get("owner", "")),
            rmf_functions=_str_list(raw.get("rmf_functions")),
            monitoring=monitoring or {},
            provisional_move=move or {},
            response_ladder={str(k): str(v) for k, v in (ladder_raw or {}).items()},
            raw=raw,
        )

    @property
    def telemetry_kris(self) -> list[str]:
        return _str_list(self.monitoring.get("telemetry_kris"))

    @property
    def max_band_90ci(self) -> Optional[list[float]]:
        return _ci(self.provisional_move.get("max_band_90ci"))

    @property
    def moved_factor(self) -> str:
        return str(self.provisional_move.get("factor", ""))

    @property
    def disposition_sla_hours(self) -> Optional[int]:
        v = self.provisional_move.get("disposition_sla_hours")
        return int(v) if isinstance(v, (int, float)) else None

    @property
    def missing_ladder_rungs(self) -> list[str]:
        return [r for r in LADDER_RUNGS if r not in self.response_ladder]

    @property
    def ladder_complete(self) -> bool:
        return not self.missing_ladder_rungs


@dataclass
class AgentRecord:
    """One entry of the security-fed detected-agent set (§0.H seam)."""

    id: str
    description: str
    first_detected: Optional[dt.date]
    source: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, aid: str, raw: dict[str, Any]) -> "AgentRecord":
        return cls(
            id=aid,
            description=str(raw.get("description", "")),
            first_detected=_as_date(raw.get("first_detected")),
            source=str(raw.get("source", "")),
            raw=raw,
        )


@dataclass
class Deviation:
    """A guardrail deviation (§0.E): a *provisional* exception, machine-proposed
    and awaiting (or past) human disposition. Wraps the shape-compatible
    :class:`IssueRecord` and reads the deviation-specific fields from ``.raw``.
    Lives in ``guardrail_events/``, never ``issues/`` — so the eng residual
    cannot see it (P.4)."""

    record: IssueRecord

    @classmethod
    def parse(cls, raw: dict[str, Any], path: str) -> "Deviation":
        return cls(record=IssueRecord.parse(raw, path))

    # -- shared shape -------------------------------------------------------
    @property
    def id(self) -> str:
        return self.record.id

    @property
    def title(self) -> str:
        return self.record.title

    @property
    def filed_on(self) -> Optional[dt.date]:
        return self.record.filed_on

    @property
    def mapped_scenarios(self) -> list[str]:
        return self.record.mapped_scenarios

    @property
    def moves(self) -> str:
        return self.record.moves

    @property
    def with_ci_90ci(self) -> Optional[list[float]]:
        return self.record.with_ci_90ci

    # -- deviation-specific (.raw) ------------------------------------------
    @property
    def guardrail(self) -> str:
        return str(self.record.raw.get("guardrail", ""))

    @property
    def disposition(self) -> str:
        return str(self.record.raw.get("disposition", ""))

    @property
    def severity(self) -> str:
        return str(self.record.raw.get("severity", ""))

    @property
    def response_invoked(self) -> str:
        return str(self.record.raw.get("response_invoked", ""))

    @property
    def detected_by(self) -> str:
        return str(self.record.raw.get("detected_by", ""))

    @property
    def disposition_due(self) -> Optional[dt.date]:
        return _as_date(self.record.raw.get("disposition_due"))

    @property
    def disposition_on(self) -> Optional[dt.date]:
        return _as_date(self.record.raw.get("disposition_on"))

    @property
    def is_open(self) -> bool:
        """Still awaiting a human decision."""
        return self.disposition == "proposed"

    @property
    def contributes(self) -> bool:
        """Counts toward the provisional overlay (§1.C): proposed or accepted."""
        return self.disposition in CONTRIBUTING_DISPOSITIONS


# ---------------------------------------------------------------------------
# Loading (§1.A). The existing graph via load_graph, then the new registers
# into new collections. The eng build path is not called through here.
# ---------------------------------------------------------------------------


def _load_register_file(path: Path, parse, errors: list[str], label: str) -> dict:
    out: dict = {}
    if not path.exists():
        return out
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML ({exc})")
        return out
    if not isinstance(raw, dict):
        errors.append(f"{path}: expected a mapping of {label}-id -> spec")
        return out
    for key, spec in raw.items():
        out[str(key)] = parse(str(key), spec or {})
    return out


def load_grc_graph(data_dir: Path) -> Graph:
    """Load the extended corpus: the assembled eng graph plus the GRC-only
    registers as new collections (``graph.regulations``, ``graph.sla``,
    ``graph.guardrails``, ``graph.agents``, ``graph.deviations``)."""
    data_dir = Path(data_dir)
    graph = load_graph(data_dir)
    errors = graph.load_errors

    graph.regulations = _load_register_file(
        data_dir / "regulations.yaml", Requirement.parse, errors, "requirement")
    graph.guardrails = _load_register_file(
        data_dir / "guardrails.yaml", Guardrail.parse, errors, "guardrail")
    graph.agents = _load_register_file(
        data_dir / "agent_inventory.yaml", AgentRecord.parse, errors, "agent")

    sla_path = data_dir / "sla_config.yaml"
    sla_raw: dict[str, Any] = {}
    if sla_path.exists():
        try:
            loaded = yaml.safe_load(sla_path.read_text())
            if isinstance(loaded, dict):
                sla_raw = loaded
            else:
                errors.append(f"{sla_path}: expected a mapping")
        except yaml.YAMLError as exc:
            errors.append(f"{sla_path}: invalid YAML ({exc})")
    graph.sla = SLAConfig.parse(sla_raw)

    # Deviations: their own directory, NEVER data/issues/ (P.4). Reuses the
    # IssueRecord shape so the engine's per-issue FAIR contribution applies.
    deviations: list[Deviation] = []
    dev_dir = data_dir / "guardrail_events"
    if dev_dir.exists():
        for path in sorted(dev_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text())
            except yaml.YAMLError as exc:
                errors.append(f"{path}: invalid YAML ({exc})")
                continue
            if not isinstance(raw, dict):
                errors.append(f"{path}: expected a mapping at the top level")
                continue
            deviations.append(Deviation.parse(raw, str(path)))
    graph.deviations = deviations
    return graph


# ---------------------------------------------------------------------------
# Derivation results (§1.B). Small typed records the render consumes. Every
# figure names its denominator; none is a composite.
# ---------------------------------------------------------------------------


@dataclass
class OverduePolicy:
    policy_id: str
    title: str
    owner: str
    last_reviewed: Optional[dt.date]
    cadence: str
    due_on: Optional[dt.date]
    days_overdue: int


@dataclass
class PolicyCurrency:
    """Denominator: every policy in policies.yaml with a review cadence
    (defaulted from sla_config when absent)."""

    total: int
    overdue: list[OverduePolicy]

    @property
    def current(self) -> int:
        return self.total - len(self.overdue)


@dataclass
class AgentCoverage:
    """Denominator: the security-fed detected-agent set (agent_inventory.yaml),
    NOT the union of guardrail applies_to (which would trivially read 100%)."""

    detected: list[str]
    covered: list[str]
    uncovered: list[str]
    governed_undetected: list[str]  # in some applies_to but not in the inventory


@dataclass
class RequirementCoverage:
    """Denominator: every requirement in regulations.yaml. Satisfied = at least
    one ``satisfied_by_controls`` id exists in controls.yaml."""

    total: int
    satisfied: list[str]
    unsatisfied: list[str]
    unknown_control_refs: list[tuple[str, str]]  # (requirement, missing control id)
    mismatched_framework_refs: list[str]  # two-directions consistency notes


@dataclass
class RiskHygiene:
    """Named risks carrying no validation flags. Criteria: the validate_graph
    flag surface (uncalibrated/stale/unknown estimator, no-op effect, threshold
    rules, scenario lifecycle problems), attributed to the risk that carries the
    flagged scenario or issue; plus register-level flags naming the risk."""

    total: int
    passing: list[str]
    flagged: dict[str, list[str]]  # nid -> flag codes


@dataclass
class RemediationSLAResult:
    """The process-failure lens: overdue remediation work and can-kicking, as
    counts and ages — deliberately NOT exposure-ranked (that is the eng tab's
    deferral view; duplicating it here would blur the two readers)."""

    total_live: int  # funded / in_progress / proposed
    overdue: list  # Remediation records with target_date < as-of
    kicked: list  # active exceptions renewed >= alert_count times
    kicked_unrefreshed: list  # of those, justification never revisited


@dataclass
class DeviationSLA:
    dev: Deviation
    due: Optional[dt.date]
    decided: Optional[dt.date]
    met: Optional[bool]  # None = still open and inside its window
    days_overdue: int = 0


@dataclass
class ProvisionalContribution:
    """One deviation's bounded FAIR contribution (§1.C): the same per-issue
    contribution the engine computes, run over the deviation's effect band
    clamped to the guardrail's ``provisional_move.max_band_90ci``."""

    dev: Deviation
    named_risk: str
    band: Band
    effective_ci: list[float]
    clamped: bool  # the authored band exceeded the guardrail bound


@dataclass
class ProvisionalExposure:
    """The Model B overlay, WIP: provisional increments against named-risk
    appetites. NEVER added to the eng portfolio total; never that risk's
    published exposure."""

    contributions: list[ProvisionalContribution]
    by_risk: dict[str, Band]  # nid -> combined provisional increment


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GRCEngine:
    """Computes the §1.B/§1.C derivations over an extended, validated graph.

    ``validate_graph`` runs here (attaching the same flags the eng CLI attaches)
    and its problem list is kept for the hygiene derivation. A
    :class:`GraphEngine` is built for the below-appetite signal and reference
    Monte Carlo choices — the eng render is never invoked.
    """

    def __init__(self, graph: Graph, config: Config):
        self.graph = graph
        self.config = config
        self.problems: list[Issue] = validate_graph(graph, config)
        self.eng = GraphEngine(graph, config)
        self.mc = MonteCarlo(iterations=config.iterations, seed=config.seed)

    # -- Governance ---------------------------------------------------------

    def _cadence_days(self, cadence: str) -> int:
        default_days = _CADENCE_DAYS.get("annual", 366)
        if self.graph.sla.policy_review_cadence_months != 12:
            default_days = round(self.graph.sla.policy_review_cadence_months * 30.5)
        return _CADENCE_DAYS.get(str(cadence).lower(), default_days)

    # Framing rule for anything cadence-derived (policies here; named-risk
    # review currency when the Risk drill-down renders it): the BUILD does the
    # checking and FLAGS records for manual review — copy must never imply the
    # program checks dates by hand. The review/sign-off is the human step.
    def policy_currency(self) -> PolicyCurrency:
        overdue: list[OverduePolicy] = []
        for pid, pol in self.graph.policies.items():
            cadence = str(pol.raw.get("review_cadence", "")) or "annual"
            if pol.last_reviewed is None:
                overdue.append(OverduePolicy(pid, pol.title, pol.owner, None, cadence, None, 0))
                continue
            window = self._cadence_days(cadence)
            due = pol.last_reviewed + dt.timedelta(days=window)
            if due < self.config.as_of:
                overdue.append(OverduePolicy(
                    pid, pol.title, pol.owner, pol.last_reviewed, cadence, due,
                    (self.config.as_of - due).days))
        overdue.sort(key=lambda o: o.days_overdue, reverse=True)
        return PolicyCurrency(total=len(self.graph.policies), overdue=overdue)

    def agent_coverage(self) -> AgentCoverage:
        detected = sorted(self.graph.agents)
        governed = {a for g in self.graph.guardrails.values() for a in g.applies_to}
        covered = [a for a in detected if a in governed]
        uncovered = [a for a in detected if a not in governed]
        governed_undetected = sorted(governed - set(detected))
        return AgentCoverage(detected, covered, uncovered, governed_undetected)

    def requirement_coverage(self) -> RequirementCoverage:
        satisfied, unsatisfied, unknown = [], [], []
        for rid, req in self.graph.regulations.items():
            known = [c for c in req.satisfied_by_controls if c in self.graph.controls]
            unknown.extend((rid, c) for c in req.satisfied_by_controls if c not in self.graph.controls)
            (satisfied if known else unsatisfied).append(rid)
        # Two-directions consistency: controls.framework_refs must mirror
        # regulations.satisfied_by_controls (find-the-number-in-two-places).
        mismatches: list[str] = []
        forward: dict[str, set[str]] = {}
        for rid, req in self.graph.regulations.items():
            for cid in req.satisfied_by_controls:
                forward.setdefault(cid, set()).add(rid)
        for cid, ctrl in self.graph.controls.items():
            refs = set(_str_list(ctrl.raw.get("framework_refs")))
            fwd = forward.get(cid, set())
            for rid in refs - fwd:
                mismatches.append(f"{cid} names {rid} but {rid} does not list {cid}")
            for rid in fwd - refs:
                mismatches.append(f"{rid} lists {cid} but {cid} does not name {rid}")
        return RequirementCoverage(
            total=len(self.graph.regulations), satisfied=satisfied,
            unsatisfied=unsatisfied, unknown_control_refs=unknown,
            mismatched_framework_refs=sorted(mismatches))

    # -- Risk ---------------------------------------------------------------

    def risk_hygiene(self) -> RiskHygiene:
        flagged: dict[str, list[str]] = {}

        def tag(nid: str, code: str) -> None:
            if nid in self.graph.named_risks:
                flagged.setdefault(nid, []).append(code)

        for sid, sc in self.graph.scenarios.items():
            for p in sc.problems:
                if p.severity == "flag":
                    tag(sc.named_risk, p.code)
        for issue in self.graph.issues:
            resolved = self.graph.resolved_scenarios(issue)
            nid = ""
            if resolved and resolved[0] in self.graph.scenarios:
                nid = self.graph.scenarios[resolved[0]].named_risk
            for p in issue.problems:
                if p.severity == "flag" and nid:
                    tag(nid, p.code)
        for p in self.problems:  # register-level flags naming the risk directly
            if p.severity != "flag":
                continue
            head = p.message.split(":", 1)[0].strip()
            if head in self.graph.named_risks:
                tag(head, p.code)
        passing = [nid for nid in self.graph.named_risks if nid not in flagged]
        return RiskHygiene(total=len(self.graph.named_risks), passing=passing, flagged=flagged)

    def unscored_risks(self) -> list[str]:
        """Named risks with zero scenarios — registered but never quantified."""
        return [nid for nid in self.graph.named_risks
                if not self.graph.scenarios_of_named_risk.get(nid)]

    def remediation_sla(self) -> RemediationSLAResult:
        live = [r for r in self.graph.remediations if r.is_active]
        overdue = sorted(
            (r for r in live if r.target_date and r.target_date < self.config.as_of),
            key=lambda r: r.target_date)
        kicked = [i for i in self.graph.issues
                  if i.type == "exception" and i.is_active
                  and i.renewal_count >= self.config.renewal_alert_count]
        unrefreshed = [i for i in kicked if not i.justification_changed_last]
        return RemediationSLAResult(
            total_live=len(live), overdue=overdue, kicked=kicked,
            kicked_unrefreshed=unrefreshed)

    # -- Compliance ---------------------------------------------------------

    def unmapped_controls(self) -> tuple[list[str], list[str]]:
        """Two precise denominators, never blended: controls tracing to no
        governing POLICY, and controls mapped to no NAMED RISK."""
        no_policy = [cid for cid, c in self.graph.controls.items()
                     if not c.policy or c.policy not in self.graph.policies]
        no_risk = [cid for cid, c in self.graph.controls.items()
                   if not c.mapped_named_risks]
        return no_policy, no_risk

    def findings_without_plan(self) -> list[IssueRecord]:
        addressed = {iid for r in self.graph.remediations for iid in r.addresses_issues}
        return [i for i in self.graph.issues
                if i.type == ISSUE_FINDING and i.id not in addressed]

    def evidence_freshness(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {"fresh": [], "stale": [], "missing": []}
        for eid, ev in self.graph.evidence.items():
            out[ev.status(self.config.as_of)].append(eid)
        return out

    def manual_evidence(self) -> list[str]:
        return [eid for eid, ev in self.graph.evidence.items()
                if ev.collection_method.lower() == "manual"]

    def cross_framework_reuse(self) -> dict[str, list[str]]:
        """Controls satisfying more than one external requirement — the
        map-once-satisfy-many efficiency read (a positive finding)."""
        by_control: dict[str, list[str]] = {}
        for rid, req in self.graph.regulations.items():
            for cid in req.satisfied_by_controls:
                if cid in self.graph.controls:
                    by_control.setdefault(cid, []).append(rid)
        return {cid: rids for cid, rids in sorted(by_control.items()) if len(rids) > 1}

    def over_engineered_controls(self) -> list[tuple[str, list[str]]]:
        """Controls whose every computed mapped risk sits BELOW appetite —
        over-invested relative to declared tolerance. Two-sided RAG (P.9):
        these carry amber (--status-below) and the word "over-controlled",
        never green. Distinct from cross-framework reuse."""
        states = {r.named_risk.id: r.state for r in self.eng.all_named_risk_residuals()}
        out = []
        for cid, ctrl in self.graph.controls.items():
            mapped = [n for n in ctrl.mapped_named_risks if n in states]
            if mapped and all(states[n] == RAG_BELOW for n in mapped):
                out.append((cid, mapped))
        return out

    # -- AI governance (under Governance) -----------------------------------

    def deviations_by(self) -> dict[str, dict[str, int]]:
        by_disposition: dict[str, int] = {d: 0 for d in DISPOSITIONS}
        by_severity: dict[str, int] = {}
        for d in self.graph.deviations:
            by_disposition[d.disposition] = by_disposition.get(d.disposition, 0) + 1
            by_severity[d.severity] = by_severity.get(d.severity, 0) + 1
        return {"disposition": by_disposition, "severity": by_severity}

    def deviation_sla(self) -> list[DeviationSLA]:
        """Time-to-DISPOSITION against each guardrail's SLA — the
        governing-at-speed number. It is time to a human decision on a
        machine-proposed record, not time-to-approval-before-action."""
        out: list[DeviationSLA] = []
        for d in self.graph.deviations:
            due, decided = d.disposition_due, d.disposition_on
            if decided is not None and due is not None:
                met: Optional[bool] = decided <= due
                days = max(0, (decided - due).days)
            elif d.is_open and due is not None:
                met = None if self.config.as_of <= due else False
                days = max(0, (self.config.as_of - due).days)
            else:
                met, days = None, 0
            out.append(DeviationSLA(dev=d, due=due, decided=decided, met=met, days_overdue=days))
        return out

    def provisional_exposure(self) -> ProvisionalExposure:
        """§1.C — the Model B overlay. Per contributing deviation (proposed or
        accepted), the engine's per-issue FAIR contribution over the deviation's
        effect band, **clamped to** the guardrail's ``provisional_move``
        bound, attributed to the mapped scenario's named risk. Provisional and
        WIP: not added to the eng portfolio, not the risk's published exposure."""
        contributions: list[ProvisionalContribution] = []
        streams_by_risk: dict[str, list[list[float]]] = {}
        for d in self.graph.deviations:
            if not d.contributes or d.with_ci_90ci is None or not d.mapped_scenarios:
                continue
            sid = d.mapped_scenarios[0]
            scn = self.graph.scenarios.get(sid)
            if scn is None:
                continue
            try:
                baseline = {
                    OPPORTUNITY_FREQUENCY: fit_distribution(
                        OPPORTUNITY_FREQUENCY, *scn.opportunity_frequency_90ci),
                    PROBABILITY_OF_REALIZATION: fit_distribution(
                        PROBABILITY_OF_REALIZATION, *scn.probability_of_realization_90ci),
                    LOSS_MAGNITUDE: fit_distribution(
                        LOSS_MAGNITUDE, *scn.loss_magnitude_90ci),
                }
            except (TypeError, ValueError):
                continue
            lo, hi = d.with_ci_90ci
            clamped = False
            rail = self.graph.guardrails.get(d.guardrail)
            max_band = rail.max_band_90ci if rail else None
            if max_band is not None:  # the meta-guardrail: a bounded auto-registrar
                new_lo, new_hi = min(lo, max_band[0]), min(hi, max_band[1])
                clamped = (new_lo, new_hi) != (lo, hi)
                lo, hi = new_lo, new_hi
            if hi <= lo:
                continue
            moved = d.moves or (rail.moved_factor if rail else "")
            try:
                with_dist = fit_distribution(moved, lo, hi)
            except (TypeError, ValueError):
                continue
            samples = self.mc.contribution_samples(
                moved=moved, baseline=baseline, with_exception=with_dist,
                key=f"grc-deviation|{d.id}")
            nid = scn.named_risk
            contributions.append(ProvisionalContribution(
                dev=d, named_risk=nid, band=Band.from_samples(samples),
                effective_ci=[lo, hi], clamped=clamped))
            streams_by_risk.setdefault(nid, []).append(samples)
        by_risk = {nid: Band.from_samples(self.mc.sum_streams(streams))
                   for nid, streams in streams_by_risk.items()}
        return ProvisionalExposure(contributions=contributions, by_risk=by_risk)

    def ladder_completeness(self) -> tuple[list[str], dict[str, list[str]]]:
        complete = [gid for gid, g in self.graph.guardrails.items() if g.ladder_complete]
        incomplete = {gid: g.missing_ladder_rungs
                      for gid, g in self.graph.guardrails.items() if not g.ladder_complete}
        return complete, incomplete

    # -- AI & Operational Excellence ----------------------------------------

    def finding_sources(self) -> dict[str, int]:
        """The self-reported-vs-found three-way (self-identified / audit /
        incident-PMAI). Presented with a small-n note by the render; never
        collapsed to a two-way."""
        out: dict[str, int] = {}
        for i in self.graph.issues:
            if i.type == ISSUE_FINDING:
                out[i.source or "unknown"] = out.get(i.source or "unknown", 0) + 1
        return out

    # -- Landing (§1.E) -----------------------------------------------------

    def program_sla(self) -> dict[str, tuple[int, int]]:
        """One program-wide SLA-adherence read across the measurable process
        steps, each named with its own denominator (no composite index — this
        is a sum of like-for-like met/measured counts, stated per step)."""
        pc = self.policy_currency()
        ev = self.evidence_freshness()
        rem = self.remediation_sla()
        dev = self.deviation_sla()
        dev_measured = [s for s in dev if s.met is not None]
        return {
            "Policy reviews on cadence": (pc.current, pc.total),
            "Evidence fresh on cadence": (len(ev["fresh"]), len(self.graph.evidence)),
            "Remediations on target date": (rem.total_live - len(rem.overdue), rem.total_live),
            "Deviations dispositioned in SLA": (
                sum(1 for s in dev_measured if s.met), len(dev_measured)),
        }
