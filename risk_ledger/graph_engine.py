"""The v2 engine: aggregation, appetite, RAG banding, control health (SPEC §4).

Reuses the FAIR-shaped Monte Carlo (`montecarlo.py`) unchanged. Anchors the
baseline at Tier 3 (the scenario), computes the marginal contribution of each
factor-moving issue, and aggregates residual **up** the tree:

    scenario  ->  named risk  ->  domain  ->  portfolio

Four rules from SPEC §4 govern the whole module:

1. **One path into residual.** Only ``exception`` and ``vuln`` issues move a
   factor and enter the bands. ``finding`` severity, control health, evidence
   freshness, and KRIs inform the estimate/narrative but never add a term.
2. **Appetite is a two-sided target.** Three gates in order (SPEC v2.6 §1, see
   ``rag_band``): mean at/past appetite -> red; a breach probability at/past
   ``p_red`` -> red; otherwise a mean in the top quarter of tolerance -> green
   (the only green), below that -> amber. Both parameters are configurable per
   enterprise. The old straddle branch is gone (v2.5 §1): a wide tail can no
   longer paint a low-mean risk green.
3. **Honest uncertainty, surfaced separately.** Emerging scenarios (wide, moving
   intervals) are computed but held OUT of the appetite-tested aggregate.
4. **Capacity vs appetite.** The rolled-up portfolio aggregate is compared to the
   declared appetite (a revenue-percent line) and, separately, to the hard
   capacity/materiality line. Domains are monitored rollups with no ceiling.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .config import Config
from .graph import Graph
from .models import (
    Control,
    Domain,
    IssueRecord,
    NamedRisk,
    Scenario,
)
from .montecarlo import (
    OPPORTUNITY_FREQUENCY,
    LOSS_MAGNITUDE,
    PROBABILITY_OF_REALIZATION,
    VARIABLES,
    Band,
    Distribution,
    MonteCarlo,
    fit_distribution,
)

# RAG banding states (the two-sided appetite target, SPEC §4). These map to the
# three status tokens: over -> --status-over (red), at -> --status-at (green),
# below -> --status-below (amber). Distinct from the emerging track's amber.
RAG_OVER = "over"
RAG_AT = "at"
RAG_BELOW = "below"

# Control-health RAG (derived, diagnostic only; never re-enters residual).
HEALTH_GREEN = "green"
HEALTH_AMBER = "amber"
HEALTH_RED = "red"

# Severity weights for the control-health burden. A finding carries its bounded
# severity; an accepted exception/vuln on the control is an open gap weighted at
# medium. These calibrate the green/amber/red thresholds below.
_SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_GAP_WEIGHT = 2
_HEALTH_RED_AT = 6   # burden at/above this -> red (e.g. two highs, or critical+high)
_HEALTH_AMBER_AT = 2  # burden at/above this (but below red) -> amber

DEFAULT_GREEN_FLOOR = 0.75  # gate 2: mean >= 75% of appetite reads green (SPEC v2.6 §1)
DEFAULT_P_RED = 0.33        # gate 1: P(loss > appetite) >= 1/3 reads red, whatever the mean (SPEC v2.6 §1)


def rag_band(
    mean: float,
    threshold: float,
    p_exceed: float,
    *,
    floor: float = DEFAULT_GREEN_FLOOR,
    p_red: float = DEFAULT_P_RED,
) -> str:
    """Appetite RAG (SPEC v2.6 §1). Three gates, evaluated in order.

    * Gate 0 (position, ceiling) -- ``mean >= threshold`` -> ``over`` (red).
      Expected loss at or past declared tolerance IS the breach, full stop: this
      is not a probability question, because appetite is a statement about
      expected annual loss.
    * Gate 1 (danger)            -- ``p_exceed >= p_red`` -> ``over`` (red). A
      reasonably probable breach is the actionable fact regardless of the mean.
    * Gate 2 (efficiency)        -- among risks unlikely to breach and under the
      line, ``mean >= floor × threshold`` -> ``at`` (green, using the declared
      tolerance), else ``below`` (amber, unused tolerance).

    Gates 0 and 1 are independent and neither subsumes the other. A fat-tailed
    risk (median << mean) can exceed appetite in expectation while its breach
    probability stays modest; a wide-banded risk can sit under appetite in
    expectation with a probable breach. Different failures; both are red. (This
    reasoning is the thing most likely to be "simplified" away by a later reader,
    which is exactly why it lives here.)

    Colour is position, probability is tail, and one never decides the other:
    green is bounded BELOW by the mean floor ("are you using it?") and ABOVE by
    both the appetite line and the breach probability ("are you about to blow
    through it?"). The old straddle branch — a wide right tail turning a low-mean
    risk green — is gone (SPEC v2.5 §1). Green also requires controlled
    uncertainty: a mean at 85% with bands wide enough to push p_exceed past p_red
    reads red, which is emergent, not bolted on.
    """
    if mean >= threshold:            # gate 0: position ceiling — a mean past the line IS the breach
        return RAG_OVER
    if p_exceed >= p_red:            # gate 1: reasonably probable breach
        return RAG_OVER
    if mean >= floor * threshold:    # gate 2: using declared tolerance
        return RAG_AT
    return RAG_BELOW                 # unused tolerance


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass
class Contribution:
    issue: IssueRecord
    band: Band


@dataclass
class ScenarioResidual:
    scenario: Scenario
    baseline: Band
    band: Band
    contributors: list[Contribution] = field(default_factory=list)  # trusted, in-band
    untrusted: list[Contribution] = field(default_factory=list)     # held out of the band


def _p_exceed(samples: list[float], line: float) -> float:
    """Share of simulated trials in which the exposure crosses ``line`` -- the
    exceedance probability (SPEC v2.2 §E). Just another read of the same
    distribution; no new path into residual."""
    if not samples:
        return 0.0
    return sum(1 for s in samples if s > line) / len(samples)


@dataclass
class NamedRiskResidual:
    named_risk: NamedRisk
    band: Band
    state: str  # RAG: over | at | below
    threshold: float
    p_over_threshold: float = 0.0  # exceedance probability against its own appetite
    scenario_ids: list[str] = field(default_factory=list)
    # Top drivers for "what is driving each" (SPEC §6 view 1): the biggest
    # factor-moving issues by expected contribution, across the risk's scenarios.
    drivers: list[Contribution] = field(default_factory=list)

    @property
    def p_over_appetite(self) -> float:
        """P(loss > appetite) — the tail surfaced beside the position (SPEC v2.5
        §2c). The threshold *is* the risk's appetite, so this aliases
        ``p_over_threshold`` under the name the rule speaks in."""
        return self.p_over_threshold


@dataclass(frozen=True)
class ResidualResult:
    """A named risk's residual under a counterfactual funding set (SPEC v3.0 §2):
    the post-funding band, mean, breach probability and RAG state, plus the ids of
    the exceptions the funded plans clear on this risk's own scenarios."""

    band: Band
    p_over_appetite: float
    state: str
    cleared: tuple[str, ...] = ()

    @property
    def mean(self) -> float:
        return self.band.mean


@dataclass(frozen=True)
class FundingPlan:
    """The smallest set of remediations that brings a risk to AT-or-better, decided
    by the engine (SPEC v3.0 §2): the ordered ids, the post-funding result, and
    whether it actually reaches within appetite."""

    remediation_ids: tuple[str, ...]
    result: ResidualResult
    sufficient: bool


@dataclass
class DomainRollup:
    domain: Domain
    band: Band  # monitored; no hard per-domain ceiling (SPEC §4)
    named_risk_ids: list[str] = field(default_factory=list)
    # A rollup of the constituent named risks' RAG STATES -- not a per-domain
    # dollar ceiling (SPEC v2.1 §D2). Lets "this domain is amber end to end"
    # be a real, checkable statement without introducing arbitrary budgeting.
    rag_counts: dict[str, int] = field(default_factory=dict)

    @property
    def amber_end_to_end(self) -> bool:
        """Every constituent named risk reads BELOW (amber) -- the standout
        "over-controlled domain" story (SPEC v2.1 §E story 9)."""
        return bool(self.named_risk_ids) and self.rag_counts.get(RAG_BELOW, 0) == len(self.named_risk_ids)


@dataclass
class PortfolioResult:
    band: Band                    # managed, appetite-tested aggregate
    appetite: Optional[float]     # declared appetite (revenue-percent line)
    appetite_state: str           # RAG vs declared appetite (the single position)
    capacity: Optional[float]     # hard audit-materiality line
    over_appetite: bool           # bottom-up aggregate exceeds declared appetite (the signal)
    # Exceedance probabilities: the honest read of a band against a line (SPEC
    # v2.2 §E). For a hard line the tail is the question, not the mean.
    p_over_appetite: float = 0.0
    p_over_capacity: float = 0.0


@dataclass
class ControlHealthResult:
    control: Control
    health: str                   # green | amber | red
    burden: float                 # severity-weighted open-issue load
    findings_by_severity: dict[str, int]
    open_gap_count: int           # open exceptions/vulns on the control
    evidence_status: str          # fresh | stale | missing | none
    clean_but_unproven: bool      # green on findings, amber only from stale/missing evidence


@dataclass
class EmergingItem:
    scenario: Scenario
    band: Band                    # the wide, moving interval
    trajectory: str
    would_breach: bool            # upper bound exceeds its named risk's appetite
    threshold: Optional[float]


@dataclass
class KRISignal:
    kri_id: str
    title: str
    status: str  # ok | amber | breached


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GraphEngine:
    """Computes the residual aggregation, appetite, RAG bands, and control health
    over an assembled, validated :class:`Graph`.

    ``validate_graph`` must have run first, so trust flags are attached and
    ``IssueRecord.counts_in_bands`` is meaningful.
    """

    def __init__(self, graph: Graph, config: Config):
        self.graph = graph
        self.config = config
        self.mc = MonteCarlo(iterations=config.iterations, seed=config.seed)
        self.green_floor = (
            graph.enterprise.green_band_floor if graph.enterprise else DEFAULT_GREEN_FLOOR
        )
        self.p_red = (
            graph.enterprise.appetite_red_prob if graph.enterprise else DEFAULT_P_RED
        )

        self._scn_dists: dict[str, dict[str, Distribution]] = {}
        self._scn_baseline: dict[str, list[float]] = {}
        self._contrib_samples: dict[str, list[float]] = {}
        self._contrib_band: dict[str, Band] = {}
        self._scn_residual: dict[str, ScenarioResidual] = {}
        self._scn_residual_samples: dict[str, list[float]] = {}

        self._compute_scenarios()
        self._compute_contributions()
        self._compute_scenario_residuals()

    # -- scenario baselines -------------------------------------------------

    def _compute_scenarios(self) -> None:
        for sid, scn in self.graph.scenarios.items():
            dists = self._fit(scn)
            if dists is None:
                continue
            self._scn_dists[sid] = dists
            self._scn_baseline[sid] = self.mc.ale_samples(
                dists[OPPORTUNITY_FREQUENCY],
                dists[PROBABILITY_OF_REALIZATION],
                dists[LOSS_MAGNITUDE],
                key=f"scn-baseline|{sid}",
            )

    def _fit(self, scn: Scenario) -> Optional[dict[str, Distribution]]:
        try:
            return {
                OPPORTUNITY_FREQUENCY: fit_distribution(OPPORTUNITY_FREQUENCY, *scn.opportunity_frequency_90ci),
                PROBABILITY_OF_REALIZATION: fit_distribution(
                    PROBABILITY_OF_REALIZATION, *scn.probability_of_realization_90ci
                ),
                LOSS_MAGNITUDE: fit_distribution(LOSS_MAGNITUDE, *scn.loss_magnitude_90ci),
            }
        except (ValueError, TypeError):
            return None  # malformed baseline; validation reports it

    def scenario_is_computable(self, sid: str) -> bool:
        return sid in self._scn_dists

    # -- issue contributions (factor-moving only; primary-scenario rollup) ---

    def _compute_contributions(self) -> None:
        for issue in self.graph.issues:
            if not issue.is_computable or not issue.moves_a_factor or not issue.is_active:
                continue
            sid = self._primary_scenario(issue)
            if sid is None or sid not in self._scn_dists:
                continue
            if issue.moves not in VARIABLES or issue.with_ci_90ci is None:
                continue
            try:
                issue_dist = fit_distribution(issue.moves, *issue.with_ci_90ci)
            except (ValueError, TypeError):
                continue
            samples = self.mc.contribution_samples(
                moved=issue.moves,
                baseline=self._scn_dists[sid],
                with_exception=issue_dist,
                key=f"graph-contrib|{issue.id}",
            )
            self._contrib_samples[issue.id] = samples
            self._contrib_band[issue.id] = Band.from_samples(samples)

    def _primary_scenario(self, issue: IssueRecord) -> Optional[str]:
        """First mapped scenario is primary for rollup attribution (SPEC §3)."""
        resolved = self.graph.resolved_scenarios(issue)
        return resolved[0] if resolved else None

    def contribution_band(self, issue_id: str) -> Optional[Band]:
        return self._contrib_band.get(issue_id)

    def combined_contribution_band(self, issue_ids: list[str]) -> Optional[Band]:
        """Combined residual contribution of a set of factor-moving issues, as a
        band (used by the drift view's two-ledger footprints, SPEC v2.2 §C2)."""
        streams = [self._contrib_samples[i] for i in issue_ids if i in self._contrib_samples]
        if not streams:
            return None
        return Band.from_samples(self.mc.sum_streams(streams))

    def has_contribution(self, issue_id: str) -> bool:
        return issue_id in self._contrib_samples

    # -- scenario residuals -------------------------------------------------

    def _compute_scenario_residuals(self) -> None:
        # Group factor-moving issues by their primary scenario.
        by_scn: dict[str, list[IssueRecord]] = defaultdict(list)
        for issue in self.graph.issues:
            if not issue.is_active or not issue.moves_a_factor or not issue.is_computable:
                continue
            sid = self._primary_scenario(issue)
            if sid is not None:
                by_scn[sid].append(issue)
        # kept so the what-if (residual_if_funded) can re-sum a scenario over a
        # counterfactual exception set without a second path into residual.
        self._issues_by_scn = by_scn

        for sid in self._scn_dists:
            scn = self.graph.scenarios[sid]
            baseline_samples = self._scn_baseline[sid]
            trusted: list[Contribution] = []
            untrusted: list[Contribution] = []
            streams = [baseline_samples]
            for issue in by_scn.get(sid, []):
                samples = self._contrib_samples.get(issue.id)
                if samples is None:
                    continue
                band = self._contrib_band[issue.id]
                if issue.counts_in_bands:
                    trusted.append(Contribution(issue, band))
                    streams.append(samples)
                else:
                    untrusted.append(Contribution(issue, band))
            residual_samples = self.mc.sum_streams(streams)
            self._scn_residual_samples[sid] = residual_samples
            trusted.sort(key=lambda c: c.band.mean, reverse=True)
            untrusted.sort(key=lambda c: c.band.mean, reverse=True)
            self._scn_residual[sid] = ScenarioResidual(
                scenario=scn,
                baseline=Band.from_samples(baseline_samples),
                band=Band.from_samples(residual_samples),
                contributors=trusted,
                untrusted=untrusted,
            )

    def scenario_residual(self, sid: str) -> Optional[ScenarioResidual]:
        return self._scn_residual.get(sid)

    def _managed_scenarios_of(self, nid: str) -> list[str]:
        """Computable, MANAGED scenarios under a named risk (emerging held out)."""
        return [
            sid
            for sid in self.graph.scenarios_of_named_risk.get(nid, [])
            if sid in self._scn_dists and not self.graph.scenarios[sid].is_emerging
        ]

    # -- named-risk aggregation + RAG ---------------------------------------

    def named_risk_residual(self, nid: str) -> Optional[NamedRiskResidual]:
        nr = self.graph.named_risks.get(nid)
        if nr is None or nr.appetite_threshold is None:
            return None
        scn_ids = self._managed_scenarios_of(nid)
        if not scn_ids:
            return None  # only emerging scenarios (surfaced separately) or none
        samples = self.mc.sum_streams([self._scn_residual_samples[sid] for sid in scn_ids])
        band = Band.from_samples(samples)
        drivers: list[Contribution] = []
        for sid in scn_ids:
            drivers.extend(self._scn_residual[sid].contributors)
        drivers.sort(key=lambda c: c.band.mean, reverse=True)
        p_over = _p_exceed(samples, nr.appetite_threshold)
        return NamedRiskResidual(
            named_risk=nr,
            band=band,
            state=rag_band(band.mean, nr.appetite_threshold, p_over,
                           floor=self.green_floor, p_red=self.p_red),
            threshold=nr.appetite_threshold,
            p_over_threshold=p_over,
            scenario_ids=scn_ids,
            drivers=drivers[:5],
        )

    def all_named_risk_residuals(self) -> list[NamedRiskResidual]:
        out = [self.named_risk_residual(nid) for nid in self.graph.named_risks]
        return [r for r in out if r is not None]

    def _named_risk_samples(self, nid: str) -> Optional[list[float]]:
        scn_ids = self._managed_scenarios_of(nid)
        if not scn_ids:
            return None
        return self.mc.sum_streams([self._scn_residual_samples[sid] for sid in scn_ids])

    # -- remediation what-if: residual if a plan were funded (SPEC v3.0 §2) ---

    def _cleared_issue_ids(self, rem) -> set[str]:
        """The active issues a restore clears — every issue on the control it
        restores. Restoring a control clears *that control's* exceptions/vulns,
        not just a nominated one."""
        if rem.type == "restore" and rem.restores_control:
            return {i.id for i in self.graph.issues if rem.restores_control in i.controls}
        return set()

    def remediations_for_risk(self, nid: str, statuses: Optional[set[str]] = None) -> list:
        """Remediations whose funding would move ``nid``'s residual: a restore that
        clears an issue on one of its managed scenarios, or a strengthen mapped to
        it. Optionally filtered by status (e.g. only the unfunded ``proposed``)."""
        on_risk = {i.id for sid in self._managed_scenarios_of(nid)
                   for i in self._issues_by_scn.get(sid, [])}
        out = []
        for r in self.graph.remediations:
            if statuses is not None and r.status not in statuses:
                continue
            if r.type == "restore" and (self._cleared_issue_ids(r) & on_risk):
                out.append(r)
            elif r.type == "strengthen" and r.mapped_risk == nid:
                out.append(r)
        return out

    def residual_if_funded(self, nid: str, remediation_ids) -> Optional[ResidualResult]:
        """Recompute ``nid``'s residual as if the given remediations were funded.

        A ``restore`` removes its control's exceptions from the affected scenarios;
        a ``strengthen`` replaces the moved factor with its ``post_control_90ci``
        band. Then run the SAME Monte Carlo over the reduced/altered exception set
        and re-aggregate to the named risk (identical ``rag_band``, v2.6). This is
        not a new model — it is the existing one path into residual, run over a
        counterfactual exception input. An empty list returns the live residual."""
        nr = self.graph.named_risks.get(nid)
        if nr is None or nr.appetite_threshold is None:
            return None
        scn_ids = self._managed_scenarios_of(nid)
        if not scn_ids:
            return None
        ids = set(remediation_ids)
        rems = [r for r in self.graph.remediations if r.id in ids]
        cleared: set[str] = set()
        strengthen: dict[str, tuple[str, list[float]]] = {}
        for r in rems:
            cleared |= self._cleared_issue_ids(r)
            if r.type == "strengthen" and r.moves and r.post_control_90ci:
                sid = self._primary_scenario_of_risk(nid)
                if sid is not None:
                    strengthen[sid] = (r.moves, r.post_control_90ci)

        cleared_here: set[str] = set()
        per = []
        for sid in scn_ids:
            if sid in strengthen:
                per.append(self._strengthened_scenario_samples(sid, *strengthen[sid], cleared))
                continue
            streams = [self._scn_baseline[sid]]
            for issue in self._issues_by_scn.get(sid, []):
                if issue.id in cleared:
                    cleared_here.add(issue.id)
                    continue
                s = self._contrib_samples.get(issue.id)
                if s is not None:
                    streams.append(s)
            per.append(self.mc.sum_streams(streams))
        samples = self.mc.sum_streams(per)
        band = Band.from_samples(samples)
        p = _p_exceed(samples, nr.appetite_threshold)
        state = rag_band(band.mean, nr.appetite_threshold, p,
                         floor=self.green_floor, p_red=self.p_red)
        return ResidualResult(band=band, p_over_appetite=p, state=state,
                              cleared=tuple(sorted(cleared_here)))

    def _primary_scenario_of_risk(self, nid: str) -> Optional[str]:
        scn = self._managed_scenarios_of(nid)
        return scn[0] if scn else None

    def _strengthened_scenario_samples(self, sid, factor, band, cleared) -> list[float]:
        """Re-price one scenario with its ``factor`` distribution swapped for the
        strengthen's post-control band, then re-add its non-cleared exceptions —
        still the one path (``ale_samples`` + the existing contributions)."""
        dists = dict(self._scn_dists[sid])
        dists[factor] = fit_distribution(factor, band[0], band[1])
        baseline = self.mc.ale_samples(
            dists[OPPORTUNITY_FREQUENCY], dists[PROBABILITY_OF_REALIZATION],
            dists[LOSS_MAGNITUDE], key=f"{sid}|strengthen")
        streams = [baseline]
        for issue in self._issues_by_scn.get(sid, []):
            if issue.id in cleared:
                continue
            s = self._contrib_samples.get(issue.id)
            if s is not None:
                streams.append(s)
        return self.mc.sum_streams(streams)

    def plan_to_appetite(self, nid: str, statuses: Optional[set[str]] = None) -> Optional[FundingPlan]:
        """The smallest set of remediations (drawn from ``remediations_for_risk``,
        optionally status-filtered) that brings ``nid`` to AT-or-better, ordered by
        single-plan dial-movement (SPEC v3.0 §2). Name the one highest-impact plan
        unless more than one is genuinely required. Returns None if the risk is not
        over appetite or has no candidate plans; ``sufficient=False`` if no set
        reaches within appetite (Type D)."""
        live = self.named_risk_residual(nid)
        if live is None or live.state != RAG_OVER:
            return None
        cands = self.remediations_for_risk(nid, statuses)
        if not cands:
            return None
        scored = []
        for r in cands:
            res = self.residual_if_funded(nid, [r.id])
            scored.append((live.band.mean - (res.band.mean if res else live.band.mean), r.id))
        scored.sort(key=lambda t: t[0], reverse=True)
        ordered = [rid for _, rid in scored]
        chosen: list[str] = []
        result = None
        for rid in ordered:
            chosen.append(rid)
            result = self.residual_if_funded(nid, chosen)
            if result and result.state != RAG_OVER:
                return FundingPlan(tuple(chosen), result, True)
        return FundingPlan(tuple(chosen), result, False) if result else None

    # -- domain rollups (monitored, no ceiling) -----------------------------

    def domain_rollup(self, did: str) -> Optional[DomainRollup]:
        domain = self.graph.domains.get(did)
        if domain is None:
            return None
        nr_ids = [
            nid
            for nid in self.graph.named_risks_of_domain.get(did, [])
            if self._named_risk_samples(nid) is not None
        ]
        if not nr_ids:
            return None
        streams = [self._named_risk_samples(nid) for nid in nr_ids]
        band = Band.from_samples(self.mc.sum_streams(streams))
        rag_counts = {RAG_OVER: 0, RAG_AT: 0, RAG_BELOW: 0}
        for nid in nr_ids:
            r = self.named_risk_residual(nid)
            if r is not None:
                rag_counts[r.state] += 1
        return DomainRollup(domain=domain, band=band, named_risk_ids=nr_ids, rag_counts=rag_counts)

    def all_domain_rollups(self) -> list[DomainRollup]:
        out = [self.domain_rollup(did) for did in self.graph.domains]
        return [r for r in out if r is not None]

    # -- portfolio: appetite vs capacity ------------------------------------

    def portfolio(self) -> Optional[PortfolioResult]:
        streams = [
            self._scn_residual_samples[sid]
            for sid in self._scn_residual_samples
            if not self.graph.scenarios[sid].is_emerging
        ]
        if not streams:
            return None
        samples = self.mc.sum_streams(streams)
        band = Band.from_samples(samples)
        ent = self.graph.enterprise
        appetite = ent.declared_appetite if ent else None
        capacity = ent.capacity_materiality if ent else None
        p_over_appetite = _p_exceed(samples, appetite) if appetite else 0.0
        # Same three-gate rule and parameters as the risk level (SPEC v2.6 §1).
        state = (rag_band(band.mean, appetite, p_over_appetite,
                          floor=self.green_floor, p_red=self.p_red)
                 if appetite else RAG_AT)
        # The position is the band-vs-appetite RAG read; the capacity read is a
        # tail probability, not a mean test (SPEC v2.2 §E2). "When the bottom-up
        # aggregate exceeds declared appetite, that is the signal."
        over_appetite = bool(appetite and band.mean > appetite)
        return PortfolioResult(
            band=band,
            appetite=appetite,
            appetite_state=state,
            capacity=capacity,
            over_appetite=over_appetite,
            p_over_appetite=p_over_appetite,
            p_over_capacity=_p_exceed(samples, capacity) if capacity else 0.0,
        )

    def negative_residuals(self) -> list[tuple[str, Band]]:
        """Scenarios or named risks whose residual band low bound is negative --
        loss exposure cannot be negative (SPEC v2.3 §B1.2). A backstop: if the
        dominance gate holds, this returns nothing, which is exactly why it is
        worth having. Computed here because it needs the residual bands."""
        out: list[tuple[str, Band]] = []
        for sid, res in self._scn_residual.items():
            if res.band.low < 0:
                out.append((sid, res.band))
        for nid in self.graph.named_risks:
            r = self.named_risk_residual(nid)
            if r is not None and r.band.low < 0:
                out.append((nid, r.band))
        return out

    def scenarios_over_capacity(self) -> list[ScenarioResidual]:
        """Managed scenarios whose residual band high crosses the enterprise
        capacity/materiality line (SPEC v2.1 §D1). A single scenario capable of
        crossing materiality is a board-level item regardless of its RAG state.
        Computed here (not in validation) because it needs the residual band."""
        ent = self.graph.enterprise
        if ent is None or ent.capacity_materiality is None:
            return []
        cap = ent.capacity_materiality
        out = [
            res for sid, res in self._scn_residual.items()
            if not self.graph.scenarios[sid].is_emerging and res.band.high > cap
        ]
        out.sort(key=lambda r: r.band.high, reverse=True)
        return out

    # -- emerging surfacing (held out of the appetite math) -----------------

    def emerging_items(self) -> list[EmergingItem]:
        out: list[EmergingItem] = []
        for sid, scn in self.graph.scenarios.items():
            if not scn.is_emerging or sid not in self._scn_residual:
                continue
            band = self._scn_residual[sid].band
            nr = self.graph.named_risks.get(scn.named_risk)
            threshold = nr.appetite_threshold if nr else None
            out.append(EmergingItem(
                scenario=scn,
                band=band,
                trajectory=scn.trajectory,
                would_breach=bool(threshold and band.high > threshold),
                threshold=threshold,
            ))
        # Widest interval first (width is the signal for an emerging item).
        out.sort(key=lambda e: e.band.high - e.band.low, reverse=True)
        return out

    # -- KRI signals + triggers ---------------------------------------------

    def kri_signals_for_scenario(self, sid: str) -> list[KRISignal]:
        return [
            KRISignal(kid, self.graph.kris[kid].title, self.graph.kris[kid].status)
            for kid in self.graph.kris_of_scenario.get(sid, [])
            if kid in self.graph.kris
        ]

    def kri_signals_for_named_risk(self, nid: str) -> list[KRISignal]:
        seen: dict[str, KRISignal] = {}
        for sid in self.graph.scenarios_of_named_risk.get(nid, []):
            for sig in self.kri_signals_for_scenario(sid):
                seen[sig.kri_id] = sig
        for kid, kri in self.graph.kris.items():  # KRIs pointing directly at the named risk
            if nid in kri.informs:
                seen[kid] = KRISignal(kid, kri.title, kri.status)
        return list(seen.values())

    def breached_kris(self) -> list[KRISignal]:
        """KRIs at/over threshold -- the triggers that widen an emerging interval
        or promote a horizon item (SPEC §4). Surfaced as signals, not a term."""
        return [
            KRISignal(kid, kri.title, kri.status)
            for kid, kri in self.graph.kris.items()
            if kri.status == "breached"
        ]

    # -- control health (derived, diagnostic; never re-enters residual) -----

    def control_health(self, cid: str) -> Optional[ControlHealthResult]:
        control = self.graph.controls.get(cid)
        if control is None:
            return None
        findings_by_sev: dict[str, int] = defaultdict(int)
        burden = 0.0
        gap_count = 0
        for issue in self.graph.issues:
            if cid not in issue.controls or not self._issue_open(issue):
                continue
            if issue.type == "finding":
                sev = issue.severity if issue.severity in _SEVERITY_WEIGHT else "low"
                findings_by_sev[sev] += 1
                burden += _SEVERITY_WEIGHT[sev]
            elif issue.moves_a_factor:  # an open, accepted exception/vuln gap
                gap_count += 1
                burden += _GAP_WEIGHT

        evidence_status = self._evidence_status(cid)
        evidence_bad = evidence_status in ("stale", "missing")

        if burden >= _HEALTH_RED_AT:
            health = HEALTH_RED
        elif burden >= _HEALTH_AMBER_AT or evidence_bad:
            health = HEALTH_AMBER
        else:
            health = HEALTH_GREEN
        clean_but_unproven = burden < _HEALTH_AMBER_AT and evidence_bad

        return ControlHealthResult(
            control=control,
            health=health,
            burden=burden,
            findings_by_severity=dict(findings_by_sev),
            open_gap_count=gap_count,
            evidence_status=evidence_status,
            clean_but_unproven=clean_but_unproven,
        )

    @staticmethod
    def _issue_open(issue: IssueRecord) -> bool:
        """An issue still weighing on a control: an active acceptance or an open
        finding (not remediated / withdrawn / closed)."""
        if issue.type == "finding":
            return issue.status not in ("closed", "remediated", "withdrawn", "resolved")
        return issue.is_active

    def _evidence_status(self, cid: str) -> str:
        """Worst evidence status over a control's evidence: missing > stale >
        fresh; ``none`` if the control has no evidence record at all."""
        eids = self.graph.evidence_of_control.get(cid, [])
        if not eids:
            return "none"
        statuses = {self.graph.evidence[e].status(self.config.as_of) for e in eids}
        for worst in ("missing", "stale", "fresh"):
            if worst in statuses:
                return worst
        return "none"

    def all_control_health(self) -> list[ControlHealthResult]:
        return [h for cid in self.graph.controls if (h := self.control_health(cid))]

    def unhealthy_controls(self) -> list[ControlHealthResult]:
        """Amber/red controls, worst first -- "where your safeguards are weakest"
        (SPEC §6 view 3). Ties broken by burden."""
        order = {HEALTH_RED: 0, HEALTH_AMBER: 1, HEALTH_GREEN: 2}
        out = [h for h in self.all_control_health() if h.health != HEALTH_GREEN]
        out.sort(key=lambda h: (order[h.health], -h.burden))
        return out
