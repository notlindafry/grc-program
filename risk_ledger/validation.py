"""The honesty gates.

Each rule exists because the matching field is where exceptions get gamed in
practice. Two tiers:

* **ERROR** -- the record is rejected and never enters a computation. The CLI
  exits non-zero so a malformed record cannot be merged silently.
* **FLAG** -- the record is kept but handled specially. A *trust* flag means the
  number cannot be believed (uncalibrated estimate, vague scope) and is kept out
  of every band; an *action* flag means the number is fine but the record is not
  actionable as written (no plan, no diversion destination) and is sent back.

The rules map onto the SPEC's "Validation rules" list one-to-one.
"""

from __future__ import annotations

import datetime as dt

from .config import Config
from .loader import Corpus
from .models import (
    ACTION,
    ERROR,
    FLAG,
    REMEDIATION_STATUSES,
    REMEDIATION_TYPES,
    STRUCTURAL,
    TRUST,
    Issue,
    Risk,
)
from .montecarlo import (
    OPPORTUNITY_FREQUENCY,
    LOSS_MAGNITUDE,
    PROBABILITY_OF_REALIZATION,
    VARIABLES,
)

# Scope strings that are not a real scope. "all internal systems" is rejected,
# not accepted -- vagueness here corrupts the magnitude side of the estimate.
_VAGUE_SCOPE_TOKENS = {"all", "*", "any", "everything", "all systems", "all internal systems", "tbd", "n/a"}

VALID_REASONS = {"resource_reallocation", "technical_constraint", "timeline", "cost", "other"}


def _valid_ci_for(variable: str, ci: list[float] | None) -> bool:
    if ci is None:
        return False
    low, high = ci
    if high <= low:
        return False
    if variable in (OPPORTUNITY_FREQUENCY, LOSS_MAGNITUDE):
        return low > 0
    if variable == PROBABILITY_OF_REALIZATION:
        return 0.0 < low < high < 1.0
    return False


def validate_risk(risk: Risk) -> list[Issue]:
    """A risk whose baseline or appetite is malformed cannot anchor any estimate."""
    issues: list[Issue] = []
    checks = {
        OPPORTUNITY_FREQUENCY: risk.opportunity_frequency_90ci,
        PROBABILITY_OF_REALIZATION: risk.probability_of_realization_90ci,
        LOSS_MAGNITUDE: risk.loss_magnitude_90ci,
    }
    for variable, ci in checks.items():
        if not _valid_ci_for(variable, ci):
            issues.append(
                Issue(
                    code="risk_baseline_invalid",
                    severity=ERROR,
                    category=STRUCTURAL,
                    message=f"{risk.id}: baseline {variable} is not a valid 90% CI: {ci!r}",
                )
            )
    if risk.appetite_threshold is None or risk.appetite_threshold <= 0:
        issues.append(
            Issue(
                code="risk_appetite_invalid",
                severity=ERROR,
                category=STRUCTURAL,
                message=f"{risk.id}: appetite_threshold must be a positive number",
            )
        )
    return issues


def validate_corpus(corpus: Corpus, config: Config) -> dict[str, list[Issue]]:
    """Validate every record in place. Returns risk-level issues by risk id."""
    risk_issues: dict[str, list[Issue]] = {}
    invalid_risks: set[str] = set()
    for rid, risk in corpus.risks.items():
        issues = validate_risk(risk)
        if issues:
            risk_issues[rid] = issues
            invalid_risks.add(rid)

    for exc in corpus.exceptions:
        _validate_exception(exc, corpus, config, invalid_risks)

    known_controls = {e.control for e in corpus.exceptions if e.control}
    for rem in corpus.remediations:
        _validate_remediation(rem, corpus, config, invalid_risks, known_controls)
    return risk_issues


def _validate_remediation(rem, corpus: Corpus, config: Config, invalid_risks: set[str],
                          known_controls: set[str]) -> None:
    """Structural gates for a remediation; never crashes the run on a bad record."""
    if not rem.id:
        rem.add(Issue("id_missing", ERROR, STRUCTURAL, f"{rem.path}: missing id"))
    if rem.type not in REMEDIATION_TYPES:
        rem.add(Issue("rem_type_invalid", ERROR, STRUCTURAL,
                      f"{rem.id}: type must be one of {', '.join(REMEDIATION_TYPES)}; got {rem.type!r}"))
    if rem.status not in REMEDIATION_STATUSES:
        rem.add(Issue("rem_status_invalid", ERROR, STRUCTURAL,
                      f"{rem.id}: status must be one of {', '.join(REMEDIATION_STATUSES)}; got {rem.status!r}"))

    if rem.type == "restore":
        if not rem.restores_control:
            rem.add(Issue("rem_restores_control_missing", ERROR, STRUCTURAL,
                          f"{rem.id}: restore requires restores_control"))
        elif rem.restores_control not in known_controls:
            rem.add(Issue("rem_restores_control_unknown", ERROR, STRUCTURAL,
                          f"{rem.id}: restores_control {rem.restores_control!r} is not a control on any exception"))
    elif rem.type == "strengthen":
        if not rem.mapped_risk:
            rem.add(Issue("rem_mapped_risk_missing", ERROR, STRUCTURAL,
                          f"{rem.id}: strengthen requires mapped_risk"))
        elif rem.mapped_risk not in corpus.risks:
            rem.add(Issue("rem_mapped_risk_unknown", ERROR, STRUCTURAL,
                          f"{rem.id}: mapped_risk {rem.mapped_risk!r} is not in risks.yaml"))
        elif rem.mapped_risk in invalid_risks:
            rem.add(Issue("rem_mapped_risk_invalid", ERROR, STRUCTURAL,
                          f"{rem.id}: mapped_risk {rem.mapped_risk!r} has a malformed baseline/appetite"))
        if rem.moves not in VARIABLES:
            rem.add(Issue("rem_moves_invalid", ERROR, STRUCTURAL,
                          f"{rem.id}: moves must be one of {', '.join(VARIABLES)}; got {rem.moves!r}"))
        elif rem.post_control_90ci is None:
            rem.add(Issue("rem_post_control_point_estimate", ERROR, STRUCTURAL,
                          f"{rem.id}: post_control_90ci must be a [low, high] 90% CI, not a point estimate"))
        elif not _valid_ci_for(rem.moves, rem.post_control_90ci):
            rem.add(Issue("rem_post_control_out_of_range", ERROR, STRUCTURAL,
                          f"{rem.id}: post_control_90ci {rem.post_control_90ci!r} is not valid for {rem.moves}"))
        # A strengthen estimate passes the same honesty gate as an exception.
        _validate_estimator(rem, corpus, config)


def _validate_exception(exc, corpus: Corpus, config: Config, invalid_risks: set[str]) -> None:
    # 1. id must be present (and should match the filename, but we only require it).
    if not exc.id:
        exc.add(Issue("id_missing", ERROR, STRUCTURAL, f"{exc.path}: missing id"))

    # 2. mapped_risk is MANDATORY and must resolve. No mapped risk, no record.
    if not exc.mapped_risk:
        exc.add(Issue("mapped_risk_missing", ERROR, STRUCTURAL, f"{exc.id}: mapped_risk is mandatory"))
    elif exc.mapped_risk not in corpus.risks:
        exc.add(
            Issue(
                "mapped_risk_unknown",
                ERROR,
                STRUCTURAL,
                f"{exc.id}: mapped_risk {exc.mapped_risk!r} is not in risks.yaml",
            )
        )
    elif exc.mapped_risk in invalid_risks:
        exc.add(
            Issue(
                "mapped_risk_invalid",
                ERROR,
                STRUCTURAL,
                f"{exc.id}: mapped_risk {exc.mapped_risk!r} has a malformed baseline/appetite",
            )
        )

    # 3. exception_effect.moves names exactly one of the three variables, and
    #    with_exception_90ci is a required, well-formed 90% CI (no point estimate).
    if exc.moves not in VARIABLES:
        exc.add(
            Issue(
                "moves_invalid",
                ERROR,
                STRUCTURAL,
                f"{exc.id}: exception_effect.moves must be one of {', '.join(VARIABLES)}; got {exc.moves!r}",
            )
        )
    else:
        if exc.with_exception_90ci is None:
            exc.add(
                Issue(
                    "with_exception_point_estimate",
                    ERROR,
                    STRUCTURAL,
                    f"{exc.id}: with_exception_90ci must be a [low, high] 90% CI, not a point estimate",
                )
            )
        elif not _valid_ci_for(exc.moves, exc.with_exception_90ci):
            exc.add(
                Issue(
                    "with_exception_out_of_range",
                    ERROR,
                    STRUCTURAL,
                    f"{exc.id}: with_exception_90ci {exc.with_exception_90ci!r} is not valid for {exc.moves}",
                )
            )

    # 4. estimated_by must resolve to a calibrated, non-stale estimator. Otherwise
    #    the number is flagged low-confidence and kept out of the trusted bands.
    _validate_estimator(exc, corpus, config)

    # 5. scope must be explicit -- an enumerated asset list or a defined population.
    _validate_scope(exc)

    # 6. remediation.target_date and mechanism are both required. Missing either
    #    flags the record as a non-plan and sends it back.
    missing = []
    if exc.remediation_target_date is None:
        missing.append("target_date")
    if not exc.remediation_mechanism:
        missing.append("mechanism")
    if missing:
        exc.add(
            Issue(
                "remediation_non_plan",
                FLAG,
                ACTION,
                f"{exc.id}: remediation has no {' and no '.join(missing)} -- a non-plan",
            )
        )

    # 7. resource_reallocation requires reason_detail.diverted_to.
    if exc.reason and exc.reason not in VALID_REASONS:
        exc.add(
            Issue(
                "reason_unknown",
                FLAG,
                ACTION,
                f"{exc.id}: reason {exc.reason!r} is not one of {', '.join(sorted(VALID_REASONS))}",
            )
        )
    if exc.reason == "resource_reallocation" and not exc.diverted_to:
        exc.add(
            Issue(
                "reallocation_no_destination",
                FLAG,
                ACTION,
                f"{exc.id}: reason is resource_reallocation but reason_detail.diverted_to is missing",
            )
        )


def _validate_estimator(exc, corpus: Corpus, config: Config) -> None:
    who = exc.estimated_by
    if not who:
        exc.add(Issue("estimator_missing", FLAG, TRUST, f"{exc.id}: no estimated_by recorded"))
        return
    estimator = corpus.estimators.get(who)
    if estimator is None:
        exc.add(
            Issue(
                "estimator_unknown",
                FLAG,
                TRUST,
                f"{exc.id}: estimated_by {who!r} is not in estimators.yaml -- treated as uncalibrated",
            )
        )
        return
    if not estimator.calibrated:
        exc.add(
            Issue(
                "estimator_uncalibrated",
                FLAG,
                TRUST,
                f"{exc.id}: estimator {who!r} is not calibrated",
            )
        )
        return
    if estimator.calibrated_on is None:
        exc.add(
            Issue(
                "estimator_no_date",
                FLAG,
                TRUST,
                f"{exc.id}: estimator {who!r} has no calibrated_on date -- recency unverifiable",
            )
        )
        return
    age_days = (config.as_of - estimator.calibrated_on).days
    if age_days > config.refresh_window_days:
        exc.add(
            Issue(
                "estimator_stale",
                FLAG,
                TRUST,
                f"{exc.id}: estimator {who!r} calibration is {age_days}d old "
                f"(refresh window {config.refresh_window_days}d)",
            )
        )


def _validate_scope(exc) -> None:
    stype = exc.scope_type
    if stype not in ("enumerated", "population"):
        exc.add(
            Issue(
                "scope_type_invalid",
                FLAG,
                TRUST,
                f"{exc.id}: scope.type must be 'enumerated' or 'population'; got {stype!r}",
            )
        )
        return
    if stype == "enumerated":
        assets = [a for a in exc.scope_assets if a.strip()]
        if not assets:
            exc.add(Issue("scope_empty", FLAG, TRUST, f"{exc.id}: enumerated scope has no assets"))
            return
        if any(a.strip().lower() in _VAGUE_SCOPE_TOKENS for a in assets):
            exc.add(
                Issue(
                    "scope_vague",
                    FLAG,
                    TRUST,
                    f"{exc.id}: scope is not explicit ({assets!r}); 'all systems' is rejected, not accepted",
                )
            )
    else:  # population
        pop = exc.scope_population.strip()
        if not pop or pop.lower() in _VAGUE_SCOPE_TOKENS:
            exc.add(
                Issue(
                    "scope_vague",
                    FLAG,
                    TRUST,
                    f"{exc.id}: population scope has no definition; vagueness corrupts the magnitude",
                )
            )
