"""Typed representations of the YAML records under version control.

Records are parsed defensively: anything structurally wrong becomes an
:class:`Issue` rather than an exception, so a single bad file never blocks a
report of the rest of the corpus. The validation gates in ``validation.py``
attach the issues; the derived properties here translate those issues into the
handling each record gets downstream.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Validation vocabulary
# ---------------------------------------------------------------------------

# Severity. An ERROR rejects the record outright (it is uncomputable or violates
# a mandatory invariant); the CLI exits non-zero when any exist. A FLAG keeps the
# record but changes how it is treated.
ERROR = "error"
FLAG = "flag"

# Flag categories.
#   TRUST  -- the *number* cannot be trusted (uncalibrated estimator, vague scope
#             that corrupts magnitude). Excluded from every computed band and
#             from rankings; surfaced separately as untrusted exposure.
#   ACTION -- the number is fine but the record cannot be actioned as it stands
#             (no remediation plan, a reallocation with no destination). Still
#             counts in the residual/drift exposure, but is pulled out of the
#             ranked action list and sent back.
TRUST = "trust"
ACTION = "action"
STRUCTURAL = "structural"  # used by ERRORs


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str  # ERROR | FLAG
    category: str  # STRUCTURAL | TRUST | ACTION
    message: str


def _as_date(value: Any) -> Optional[dt.date]:
    """Coerce a YAML scalar into a date, or None if it is not one."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------


@dataclass
class Estimator:
    email: str
    calibrated: bool
    calibrated_on: Optional[dt.date]

    @classmethod
    def parse(cls, email: str, raw: dict[str, Any]) -> "Estimator":
        return cls(
            email=email,
            calibrated=bool(raw.get("calibrated", False)),
            calibrated_on=_as_date(raw.get("calibrated_on")),
        )


@dataclass
class OKR:
    """An Objective and its Key Results, that the exceptions attach to.

    Not in the original three-file list, but the drift view's headline names the
    OKR's *objective* ("a quality microservices rebuild") and displays its key
    results as the commitments the exception footprint is eroding, which has to
    live somewhere git-native. This minimal register is that home; the optional
    ``period_end`` lets the trajectory analysis measure the run-up to a real
    deadline rather than guessing one.
    """

    id: str
    title: str
    objective: str
    key_results: list[str]
    period_end: Optional[dt.date]

    @classmethod
    def parse(cls, oid: str, raw: dict[str, Any]) -> "OKR":
        krs = raw.get("key_results") or []
        if not isinstance(krs, list):
            krs = [krs]
        return cls(
            id=oid,
            title=str(raw.get("title", oid)),
            objective=str(raw.get("objective", "")),
            key_results=[str(k) for k in krs],
            period_end=_as_date(raw.get("period_end")),
        )


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _ci(value: Any) -> Optional[list[float]]:
    """Parse a ``[low, high]`` 90% CI, returning None if it is not well-formed.

    A point estimate (a bare scalar, or ``[x]``, or ``[x, x]``) returns None on
    purpose; the validation layer turns that into an error.
    """
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    lo, hi = _num(value[0]), _num(value[1])
    if lo is None or hi is None:
        return None
    return [lo, hi]


# ---------------------------------------------------------------------------
# Remediation -- the sign-flipped counterpart of an exception
# ---------------------------------------------------------------------------

REMEDIATION_TYPES = ("restore", "strengthen")
REMEDIATION_STATUSES = ("funded", "in_progress", "proposed")
_FUNDED_STATUSES = ("funded", "in_progress")


@dataclass
class Remediation:
    """A planned control fix, version-controlled exactly like an exception.

    Two disjoint types:

    * ``restore`` -- restores a deviated control, clearing that control's active
      exceptions; the affected factors return to baseline (full restoration
      assumed), so no fresh estimate is required.
    * ``strengthen`` -- moves one factor to a new absolute band below baseline,
      gated by the same calibration rule as an exception estimate.

    Only ``funded`` and ``in_progress`` remediations count toward the
    post-remediation state.
    """

    id: str
    path: str
    raw: dict[str, Any]

    title: str = ""
    type: str = ""
    status: str = ""
    target_date: Optional[dt.date] = None
    owner: str = ""
    mechanism: str = ""  # how the fix is implemented; used for the action narrative

    # restore
    restores_control: str = ""

    # strengthen
    mapped_risk: str = ""
    moves: str = ""
    post_control_90ci: Optional[list[float]] = None
    estimated_by: str = ""
    estimated_on: Optional[dt.date] = None

    issues: list[Issue] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: dict[str, Any], path: str) -> "Remediation":
        return cls(
            id=str(raw.get("id", "")),
            path=path,
            raw=raw,
            title=str(raw.get("title", "")),
            type=str(raw.get("type", "")),
            status=str(raw.get("status", "")),
            target_date=_as_date(raw.get("target_date")),
            owner=str(raw.get("owner", "")),
            mechanism=str(raw.get("mechanism", "")),
            restores_control=str(raw.get("restores_control", "")),
            mapped_risk=str(raw.get("mapped_risk", "")),
            moves=str(raw.get("moves", "")),
            post_control_90ci=_ci(raw.get("post_control_90ci")),
            estimated_by=str(raw.get("estimated_by", "")),
            estimated_on=_as_date(raw.get("estimated_on")),
        )

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def flags(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == FLAG]

    @property
    def trust_flags(self) -> list[Issue]:
        return [i for i in self.flags if i.category == TRUST]

    @property
    def rejected(self) -> bool:
        return bool(self.errors)

    @property
    def is_computable(self) -> bool:
        return not self.rejected

    @property
    def is_active(self) -> bool:
        """A recognised, live remediation entry."""
        return self.status in REMEDIATION_STATUSES

    @property
    def is_funded(self) -> bool:
        """Counts toward the post-remediation state."""
        return self.status in _FUNDED_STATUSES

    @property
    def counts_in_bands(self) -> bool:
        """Trustworthy enough to enter a band. A restore has no estimate of its
        own (it returns to baseline), so it is trusted unless rejected; a
        strengthen passes the same calibration gate as an exception."""
        return self.is_computable and not self.trust_flags

    # -- Tier-3 (graph) linkage, additive over the legacy control link ------
    #
    # The v2 model generalises remediation linkage to many-to-many (SPEC §2.11):
    # a remediation may address scenarios and/or issues directly, alongside the
    # existing ``restores_control`` / ``mapped_risk`` levers the legacy engine
    # uses. These are parsed but not consumed by the legacy engine; the derived
    # graph reads them.
    @property
    def addresses_scenarios(self) -> list[str]:
        return _str_list(self.raw.get("addresses_scenarios"))

    @property
    def addresses_issues(self) -> list[str]:
        return _str_list(self.raw.get("addresses_issues"))

    @property
    def operational_owner(self) -> str:
        """Ticket assignee, distinct from ``owner`` (the remediation sponsor)."""
        return str(self.raw.get("operational_owner", "") or "")


# ===========================================================================
# v2 GRC-ecosystem entities (SPEC §2)
# ---------------------------------------------------------------------------
# The model spine is: Domain (Tier 1) <- NamedRisk (Tier 2) <- Scenario
# (Tier 3) <- Issue (the floor). Controls mitigate NamedRisks and trace up to
# Policies; Evidence proves Controls; KRIs inform Scenario factors; Horizon
# items watch the edge. These records are parsed here and assembled into the
# derived relational graph in ``graph.py``. The Monte Carlo and the legacy
# ``Risk``/``Exception_`` shapes above are reused unchanged (SPEC §0, §4).
# ===========================================================================


def _str_list(value: Any) -> list[str]:
    """Normalise a scalar-or-list YAML value into a list of non-empty strings."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [str(v) for v in value if str(v).strip()]


# Issue subtypes (the ``type`` discriminator, SPEC §2.5). Only the first two
# move a factor and enter the residual bands; a finding informs control health
# and the narrative but is never simulated (the "one path into residual" rule).
ISSUE_EXCEPTION = "exception"
ISSUE_VULN = "vuln"
ISSUE_FINDING = "finding"
ISSUE_TYPES = (ISSUE_EXCEPTION, ISSUE_VULN, ISSUE_FINDING)
FACTOR_MOVING_ISSUE_TYPES = (ISSUE_EXCEPTION, ISSUE_VULN)

FINDING_SEVERITIES = ("low", "medium", "high", "critical")
FINDING_SOURCES = ("audit", "incident-PMAI", "self-identified")

LIFECYCLE_STATES = ("managed", "emerging")
TRAJECTORIES = ("rising", "stable", "receding")

CONTROL_THEMES = ("Organizational", "People", "Physical", "Technological")


@dataclass
class Enterprise:
    """The top-level appetite anchor (SPEC §2.1, §4).

    Two dollar figures: ``capacity_materiality`` is the hard audit-materiality
    line the company cannot cross by choice; the declared ``appetite`` is a
    revenue-percent figure set deliberately beneath it.
    """

    revenue_annual: Optional[float]
    capacity_materiality: Optional[float]
    appetite_pct_of_revenue: Optional[float]
    green_band_floor: float = 0.75  # gate 2: mean >= 75% of appetite reads green (SPEC v2.6 §1)
    # A breach this probable is red regardless of where the mean sits (SPEC v2.6
    # §1, gate 1). p_red is floored structurally: gate 1 squeezes the top of the
    # green band from above, so a p_red set too low would collapse green even for a
    # mean sitting comfortably under appetite — controlled uncertainty is required,
    # not just good position.
    appetite_red_prob: float = 0.33
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Enterprise":
        return cls(
            revenue_annual=_num(raw.get("revenue_annual")),
            capacity_materiality=_num(raw.get("capacity_materiality")),
            appetite_pct_of_revenue=_num(raw.get("appetite_pct_of_revenue")),
            green_band_floor=_num(raw.get("green_band_floor")) or 0.75,
            appetite_red_prob=_num(raw.get("appetite_red_prob")) or 0.33,
            raw=raw,
        )

    @property
    def declared_appetite(self) -> Optional[float]:
        """``appetite_pct_of_revenue × revenue_annual`` — the board-facing line."""
        if self.revenue_annual is None or self.appetite_pct_of_revenue is None:
            return None
        return self.revenue_annual * self.appetite_pct_of_revenue


@dataclass
class Domain:
    """Tier 1 — where the risk manifests (board/portfolio altitude, SPEC §1)."""

    id: str
    title: str
    description: str
    appetite_statement: str  # board-facing narrative only, never tested against
    appetite_signed_off_by: str
    appetite_last_reviewed: Optional[dt.date]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, did: str, raw: dict[str, Any]) -> "Domain":
        return cls(
            id=did,
            title=str(raw.get("title", did)),
            description=str(raw.get("description", "")),
            appetite_statement=str(raw.get("appetite_statement", "")),
            appetite_signed_off_by=str(raw.get("appetite_signed_off_by", "")),
            appetite_last_reviewed=_as_date(raw.get("appetite_last_reviewed")),
            raw=raw,
        )


@dataclass
class NamedRisk:
    """Tier 2 — the owned, appetite-bearing risk (executive/VP altitude, SPEC §2.3)."""

    id: str
    title: str
    domain: str
    owner: str
    appetite_threshold: Optional[float]
    # Two-to-four human words for headline use — chart labels, chips, table name
    # cells (SPEC v2.4 §3 / v2 §6: IDs and foreign keys are drill-down detail,
    # never the headline). Authored, not a cosmetic filter over the ID. The full
    # ``title`` stays for drill-down text and tooltips. Falls back to ``title``.
    short_title: str = ""
    # A one-line record of WHY this appetite was set (SPEC v2.2 §D2). Appetite is
    # an authored, declared tolerance -- never derived from the residual -- and
    # the rationale makes that authorship legible on the record and in drill-down.
    appetite_rationale: str = ""
    threatens_okrs: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, nid: str, raw: dict[str, Any]) -> "NamedRisk":
        return cls(
            id=nid,
            title=str(raw.get("title", nid)),
            domain=str(raw.get("domain", "")),
            owner=str(raw.get("owner", "")),
            appetite_threshold=_num(raw.get("appetite_threshold")),
            short_title=str(raw.get("short_title", "")),
            appetite_rationale=str(raw.get("appetite_rationale", "")),
            threatens_okrs=_str_list(raw.get("threatens_okrs")),
            raw=raw,
        )

    @property
    def label(self) -> str:
        """The headline name: ``short_title`` if authored, else the full title."""
        return self.short_title or self.title


@dataclass
class Scenario:
    """Tier 3 — the quantified loss event the Monte Carlo runs on (SPEC §2.4).

    The baseline OF/PoR/LM that lived on the legacy ``risks.yaml`` moves here.
    ``legacy_risk`` lets a migrated exception (which still names a ``mapped_risk``)
    resolve to its scenario during graph assembly, so the existing corpus links
    up without rewriting every exception file.
    """

    id: str
    path: str
    title: str
    named_risk: str
    opportunity_frequency_90ci: Optional[list[float]]
    probability_of_realization_90ci: Optional[list[float]]
    loss_magnitude_90ci: Optional[list[float]]
    impact: list[str]
    vectors: list[str]
    lifecycle_state: str
    trajectory: str
    short_title: str = ""  # optional headline name; falls back to title (SPEC v3.4)
    legacy_risk: str = ""  # optional bridge to the legacy risks.yaml id
    incident: Optional[dict[str, Any]] = None  # the offline AI incident→scenario seam (SPEC §8)
    problems: list[Issue] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: dict[str, Any], path: str) -> "Scenario":
        baseline = raw.get("baseline", {}) or {}
        return cls(
            id=str(raw.get("id", "")),
            path=path,
            title=str(raw.get("title", "")),
            short_title=str(raw.get("short_title", "")),
            named_risk=str(raw.get("named_risk", "")),
            opportunity_frequency_90ci=_ci(baseline.get("opportunity_frequency_90ci")),
            probability_of_realization_90ci=_ci(baseline.get("probability_of_realization_90ci")),
            loss_magnitude_90ci=_ci(baseline.get("loss_magnitude_90ci")),
            impact=_str_list(raw.get("impact")),
            vectors=_str_list(raw.get("vectors")),
            lifecycle_state=str(raw.get("lifecycle_state", "managed")),
            trajectory=str(raw.get("trajectory", "stable")),
            legacy_risk=str(raw.get("legacy_risk", "")),
            incident=raw.get("incident") if isinstance(raw.get("incident"), dict) else None,
            raw=raw,
        )

    def add(self, issue: Issue) -> None:
        self.problems.append(issue)

    @property
    def label(self) -> str:
        """The headline name: ``short_title`` if authored, else the full title."""
        return self.short_title or self.title

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.problems if i.severity == ERROR]

    @property
    def is_emerging(self) -> bool:
        return self.lifecycle_state == "emerging"

    @property
    def baseline_by_variable(self) -> dict[str, Optional[list[float]]]:
        from .montecarlo import (
            OPPORTUNITY_FREQUENCY,
            LOSS_MAGNITUDE,
            PROBABILITY_OF_REALIZATION,
        )

        return {
            OPPORTUNITY_FREQUENCY: self.opportunity_frequency_90ci,
            PROBABILITY_OF_REALIZATION: self.probability_of_realization_90ci,
            LOSS_MAGNITUDE: self.loss_magnitude_90ci,
        }


@dataclass
class Control:
    """An ISO 27001:2022 Annex A control (SPEC §2.6). Health is derived, not stored."""

    id: str
    title: str
    theme: str
    policy: str
    mapped_named_risks: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, cid: str, raw: dict[str, Any]) -> "Control":
        return cls(
            id=cid,
            title=str(raw.get("title", cid)),
            theme=str(raw.get("theme", "")),
            policy=str(raw.get("policy", "")),
            mapped_named_risks=_str_list(raw.get("mapped_named_risks")),
            raw=raw,
        )


@dataclass
class Policy:
    """The governance layer above controls (SPEC §2.7, thin)."""

    id: str
    title: str
    owner: str
    last_reviewed: Optional[dt.date]
    link: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, pid: str, raw: dict[str, Any]) -> "Policy":
        return cls(
            id=pid,
            title=str(raw.get("title", pid)),
            owner=str(raw.get("owner", "")),
            last_reviewed=_as_date(raw.get("last_reviewed")),
            link=str(raw.get("link", "")),
            raw=raw,
        )


@dataclass
class Evidence:
    """Proof a control operates (SPEC §2.8).

    SEAM — automated evidence collection (SPEC §8): this record *is* the seam,
    and no collector is built. A real collector later populates ``last_collected``
    (and, if the schema grows, a raw artifact pointer) on each cadence tick; the
    ``status`` derivation below then flips fresh→stale→missing on its own. The
    dashboard's control-health view already reads that status as the *provability*
    signal (a control can be clean on findings yet amber because its evidence is
    stale or missing), so wiring a live source changes the inputs, not the model.
    Evidence never enters the quant — it informs control health only, keeping the
    one quantitative path (SPEC §1). Build no collector here.

    ``status`` (fresh|stale|missing) is derived from ``cadence`` + ``last_collected``.
    """

    id: str
    supports_controls: list[str]
    source: str
    collection_method: str
    cadence: str
    last_collected: Optional[dt.date]
    raw: dict[str, Any] = field(default_factory=dict)

    # cadence -> allowed age in days before the evidence is stale.
    _CADENCE_DAYS = {
        "daily": 1,
        "weekly": 7,
        "monthly": 31,
        "quarterly": 92,
        "semiannual": 184,
        "annual": 366,
    }

    @classmethod
    def parse(cls, eid: str, raw: dict[str, Any]) -> "Evidence":
        return cls(
            id=eid,
            supports_controls=_str_list(raw.get("supports_controls")),
            source=str(raw.get("source", "")),
            collection_method=str(raw.get("collection_method", "")),
            cadence=str(raw.get("cadence", "")),
            last_collected=_as_date(raw.get("last_collected")),
            raw=raw,
        )

    def status(self, as_of: dt.date) -> str:
        """fresh | stale | missing, from cadence + last_collected vs ``as_of``."""
        if self.last_collected is None:
            return "missing"
        window = self._CADENCE_DAYS.get(self.cadence.lower())
        if window is None:
            return "fresh"  # unknown cadence: cannot age it, treat as fresh
        # A grace multiple keeps a just-late collection from flipping instantly.
        return "fresh" if (as_of - self.last_collected).days <= window else "stale"


@dataclass
class KRI:
    """A key risk indicator (SPEC §2.9, thin). Informs re-estimation; never additive.

    SEAM — live KRI ingestion (SPEC §8): this record *is* the seam, and no
    ingestion is built. A real metric source later populates ``current_value``
    (and thus ``status``) on each refresh; a breach then *informs re-estimation
    of an existing factor* and *triggers emerging-risk changes* (SPEC §4), never
    adding a term of its own. On the dashboard a KRI is a light signal on a risk
    and a feed into the horizon view, not its own monitoring surface — so
    connecting a live source (Prometheus / a metrics warehouse) changes the
    inputs, not the model. Build no ingestion here.

    ``status`` (ok|amber|breached) is derived from ``current_value`` vs ``threshold``.
    """

    id: str
    title: str
    informs: list[str]
    current_value: Optional[float]
    threshold: Optional[float]
    trend: str
    direction: str = "over"  # "over" = breach when value >= threshold; "under" = when value <= threshold
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, kid: str, raw: dict[str, Any]) -> "KRI":
        return cls(
            id=kid,
            title=str(raw.get("title", kid)),
            informs=_str_list(raw.get("informs")),
            current_value=_num(raw.get("current_value")),
            threshold=_num(raw.get("threshold")),
            trend=str(raw.get("trend", "")),
            direction=str(raw.get("direction", "over")),
            raw=raw,
        )

    @property
    def status(self) -> str:
        """ok | amber | breached. Amber is the near-threshold warning band."""
        if self.current_value is None or self.threshold is None:
            return "ok"
        if self.direction == "under":
            if self.current_value <= self.threshold:
                return "breached"
            return "amber" if self.current_value <= self.threshold * 1.1 else "ok"
        if self.current_value >= self.threshold:
            return "breached"
        return "amber" if self.current_value >= self.threshold * 0.9 else "ok"


@dataclass
class HorizonItem:
    """The emerging watch list at the edge (SPEC §2.10).

    Mechanistic-test fence: an item earns a slot only if it names both a
    candidate domain and a watched KRI. Validation enforces this.
    """

    id: str
    title: str
    candidate_domain: str
    watched_kri: str
    trajectory: str
    note: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, hid: str, raw: dict[str, Any]) -> "HorizonItem":
        return cls(
            id=hid,
            title=str(raw.get("title", hid)),
            candidate_domain=str(raw.get("candidate_domain", "")),
            watched_kri=str(raw.get("watched_kri", "")),
            trajectory=str(raw.get("trajectory", "")),
            note=str(raw.get("note", "")),
            raw=raw,
        )


@dataclass
class IssueRecord:
    """The issues floor, generalised from exceptions with a ``type`` discriminator
    (SPEC §2.5). One record per individually reviewable decision.

    Three subtypes share the common fields (``id``, ``title``, ``owner``,
    ``filed_on``, ``status``, ``mapped_scenarios``, ``controls``):

    * ``exception`` — the unchanged existing schema; moves one scenario factor via
      ``exception_effect.moves`` + ``with_exception_90ci``.
    * ``vuln`` — an out-of-SLA accepted vulnerability; folds into the scenario's
      PoR via top-level ``moves`` + ``with_acceptance_90ci``.
    * ``finding`` — audit/incident/self-identified; carries a bounded ``severity``
      that informs control health and narrative but is **never simulated**.

    A legacy exception file names a single ``mapped_risk`` and a single ``control``
    rather than the new list fields; both are read here and reconciled in the graph.

    SEAM — dynamic intake / triage (SPEC §8, narrative only): this record is where
    the intake seam attaches. Today every issue is hand-authored YAML. A real
    intake workflow would sit in front of this record — raw report → suggested
    taxonomy (type, mapped scenario, moved factor, band) → a *draft* IssueRecord a
    human confirms before it lands. The confirmed output is exactly this shape, so
    the model, the quant, and the dashboard are unchanged by adding the workflow;
    only the authoring path in front of it changes. No intake machine is built here.
    """

    id: str
    path: str
    raw: dict[str, Any]
    type: str = ISSUE_EXCEPTION

    title: str = ""
    owner: str = ""
    filed_on: Optional[dt.date] = None
    status: str = "active"

    mapped_scenarios: list[str] = field(default_factory=list)  # first is primary for rollup
    mapped_risk: str = ""  # legacy single-risk link, bridged to a scenario in the graph
    controls: list[str] = field(default_factory=list)

    # exception / vuln: the moved factor and its accepted band.
    moves: str = ""
    with_ci_90ci: Optional[list[float]] = None
    estimated_by: str = ""
    estimated_on: Optional[dt.date] = None

    # exception-only narrative fields (kept intact from the legacy schema).
    okr: str = ""
    reason: str = ""
    diverted_to: Optional[str] = None
    scope_type: str = ""
    scope_assets: list[str] = field(default_factory=list)
    scope_population: str = ""
    remediation_target_date: Optional[dt.date] = None
    remediation_mechanism: str = ""
    remediation_reduces: str = ""
    renewal_count: int = 0
    justification_changed_last: Optional[str] = None
    expires_on: Optional[dt.date] = None

    # vuln-only.
    asset: str = ""

    # finding-only.
    source: str = ""
    severity: str = ""

    problems: list[Issue] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: dict[str, Any], path: str) -> "IssueRecord":
        # A legacy exception file has no ``type`` key; default to exception.
        itype = str(raw.get("type", ISSUE_EXCEPTION))
        controls = _str_list(raw.get("controls")) or _str_list(raw.get("control"))
        mapped = _str_list(raw.get("mapped_scenarios"))

        effect = raw.get("exception_effect", {}) or {}
        scope = raw.get("scope", {}) or {}
        remediation = raw.get("remediation", {}) or {}
        renewals = raw.get("renewals", {}) or {}
        reason_detail = raw.get("reason_detail", {}) or {}
        assets = scope.get("assets") or []
        if not isinstance(assets, list):
            assets = [assets]

        # The moved factor + accepted band lives in exception_effect for an
        # exception, and at the top level (with_acceptance_90ci) for a vuln.
        if itype == ISSUE_VULN:
            moves = str(raw.get("moves", "probability_of_realization"))
            with_ci = _ci(raw.get("with_acceptance_90ci"))
            estimated_by = str(raw.get("estimated_by", ""))
            estimated_on = _as_date(raw.get("estimated_on"))
        else:
            moves = str(effect.get("moves", ""))
            with_ci = _ci(effect.get("with_exception_90ci"))
            estimated_by = str(effect.get("estimated_by", ""))
            estimated_on = _as_date(effect.get("estimated_on"))

        return cls(
            id=str(raw.get("id", "")),
            path=path,
            raw=raw,
            type=itype,
            title=str(raw.get("title", "")),
            owner=str(raw.get("owner", "")),
            filed_on=_as_date(raw.get("filed_on")),
            status=str(raw.get("status", "active")),
            mapped_scenarios=mapped,
            mapped_risk=str(raw.get("mapped_risk", "")),
            controls=controls,
            moves=moves,
            with_ci_90ci=with_ci,
            estimated_by=estimated_by,
            estimated_on=estimated_on,
            okr=str(raw.get("okr", "")),
            reason=str(raw.get("reason", "")),
            diverted_to=(str(reason_detail["diverted_to"]) if reason_detail.get("diverted_to") else None),
            scope_type=str(scope.get("type", "")),
            scope_assets=[str(a) for a in assets],
            scope_population=str(scope.get("population", "")),
            remediation_target_date=_as_date(remediation.get("target_date")),
            remediation_mechanism=str(remediation.get("mechanism", "")),
            remediation_reduces=str(remediation.get("reduces", "")),
            renewal_count=int(renewals.get("count", 0) or 0),
            justification_changed_last=(
                str(renewals["justification_changed_last"])
                if renewals.get("justification_changed_last")
                else None
            ),
            expires_on=_as_date(raw.get("expires_on")),
            asset=str(raw.get("asset", "")),
            source=str(raw.get("source", "")),
            severity=str(raw.get("severity", "")),
            problems=[],
        )

    def add(self, issue: Issue) -> None:
        self.problems.append(issue)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.problems if i.severity == ERROR]

    @property
    def flags(self) -> list[Issue]:
        return [i for i in self.problems if i.severity == FLAG]

    @property
    def trust_flags(self) -> list[Issue]:
        return [i for i in self.flags if i.category == TRUST]

    @property
    def rejected(self) -> bool:
        return bool(self.errors)

    @property
    def is_computable(self) -> bool:
        return not self.rejected

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def moves_a_factor(self) -> bool:
        """Only exception and vuln change residual (the one-path rule, SPEC §4)."""
        return self.type in FACTOR_MOVING_ISSUE_TYPES

    @property
    def counts_in_bands(self) -> bool:
        return self.is_computable and self.moves_a_factor and not self.trust_flags

    @property
    def primary_scenario(self) -> str:
        """First mapped scenario — the one rollup attribution uses (SPEC §3)."""
        return self.mapped_scenarios[0] if self.mapped_scenarios else ""
