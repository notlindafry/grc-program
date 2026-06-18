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
class Risk:
    id: str
    title: str
    opportunity_frequency_90ci: Optional[list[float]]
    probability_of_realization_90ci: Optional[list[float]]
    loss_magnitude_90ci: Optional[list[float]]
    appetite_threshold: Optional[float]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, rid: str, raw: dict[str, Any]) -> "Risk":
        baseline = raw.get("baseline", {}) or {}
        return cls(
            id=rid,
            title=str(raw.get("title", rid)),
            opportunity_frequency_90ci=_ci(baseline.get("opportunity_frequency_90ci")),
            probability_of_realization_90ci=_ci(baseline.get("probability_of_realization_90ci")),
            loss_magnitude_90ci=_ci(baseline.get("loss_magnitude_90ci")),
            appetite_threshold=_num(raw.get("appetite_threshold")),
            raw=raw,
        )

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


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


@dataclass
class Exception_:
    """One filed security exception. (Trailing underscore: ``Exception`` is taken.)"""

    id: str
    path: str
    raw: dict[str, Any]

    title: str = ""
    owner: str = ""
    filed_on: Optional[dt.date] = None
    okr: str = ""
    control: str = ""
    mapped_risk: str = ""

    moves: str = ""
    with_exception_90ci: Optional[list[float]] = None
    estimated_by: str = ""
    estimated_on: Optional[dt.date] = None

    reason: str = ""
    diverted_to: Optional[str] = None

    scope_type: str = ""
    scope_assets: list[str] = field(default_factory=list)
    scope_population: str = ""

    remediation_target_date: Optional[dt.date] = None
    remediation_mechanism: str = ""
    remediation_reduces: str = ""

    status: str = "active"
    expires_on: Optional[dt.date] = None
    renewal_count: int = 0
    justification_changed_last: Optional[str] = None

    issues: list[Issue] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: dict[str, Any], path: str) -> "Exception_":
        effect = raw.get("exception_effect", {}) or {}
        reason_detail = raw.get("reason_detail", {}) or {}
        scope = raw.get("scope", {}) or {}
        remediation = raw.get("remediation", {}) or {}
        renewals = raw.get("renewals", {}) or {}
        assets = scope.get("assets") or []
        if not isinstance(assets, list):
            assets = [assets]
        return cls(
            id=str(raw.get("id", "")),
            path=path,
            raw=raw,
            title=str(raw.get("title", "")),
            owner=str(raw.get("owner", "")),
            filed_on=_as_date(raw.get("filed_on")),
            okr=str(raw.get("okr", "")),
            control=str(raw.get("control", "")),
            mapped_risk=str(raw.get("mapped_risk", "")),
            moves=str(effect.get("moves", "")),
            with_exception_90ci=_ci(effect.get("with_exception_90ci")),
            estimated_by=str(effect.get("estimated_by", "")),
            estimated_on=_as_date(effect.get("estimated_on")),
            reason=str(raw.get("reason", "")),
            diverted_to=(str(reason_detail["diverted_to"]) if reason_detail.get("diverted_to") else None),
            scope_type=str(scope.get("type", "")),
            scope_assets=[str(a) for a in assets],
            scope_population=str(scope.get("population", "")),
            remediation_target_date=_as_date(remediation.get("target_date")),
            remediation_mechanism=str(remediation.get("mechanism", "")),
            remediation_reduces=str(remediation.get("reduces", "")),
            status=str(raw.get("status", "active")),
            expires_on=_as_date(raw.get("expires_on")),
            renewal_count=int(renewals.get("count", 0) or 0),
            justification_changed_last=(
                str(renewals["justification_changed_last"])
                if renewals.get("justification_changed_last")
                else None
            ),
        )

    # -- derived handling, driven entirely by attached issues ---------------

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
    def action_flags(self) -> list[Issue]:
        return [i for i in self.flags if i.category == ACTION]

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def rejected(self) -> bool:
        """Has a hard error; excluded from every computation."""
        return bool(self.errors)

    @property
    def is_computable(self) -> bool:
        return not self.rejected

    @property
    def counts_in_bands(self) -> bool:
        """Trustworthy enough to enter a residual/drift band."""
        return self.is_computable and not self.trust_flags

    @property
    def is_well_formed(self) -> bool:
        """Clean and actionable: trustworthy number, real plan, attributable."""
        return self.counts_in_bands and not self.action_flags

    @property
    def send_back(self) -> bool:
        """Computable but flagged: return for correction before it can be actioned."""
        return self.is_computable and bool(self.flags)


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
