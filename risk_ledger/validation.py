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

from .config import Config
from .models import (
    ACTION,
    ERROR,
    FACTOR_MOVING_ISSUE_TYPES,
    FINDING_SEVERITIES,
    FINDING_SOURCES,
    FLAG,
    ISSUE_FINDING,
    ISSUE_TYPES,
    ISSUE_VULN,
    LIFECYCLE_STATES,
    STRUCTURAL,
    TRAJECTORIES,
    TRUST,
    Issue,
)
from .montecarlo import (
    OPPORTUNITY_FREQUENCY,
    LOSS_MAGNITUDE,
    PROBABILITY_OF_REALIZATION,
    VARIABLES,
)


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


def _validate_estimator(exc, corpus, config: Config) -> None:
    """Trust gate on a factor move's estimator. ``corpus`` is any object with an
    ``estimators`` mapping -- the assembled graph, in the ecosystem model."""
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


# ===========================================================================
# v2 GRC-ecosystem graph invariants (SPEC §10 Day 1, §2, §3)
# ---------------------------------------------------------------------------
# The new-model gates. Errors are structural (a link that cannot resolve, an
# uncomputable factor); flags keep the record but surface a diagnostic (an
# unmapped control's "why do we do this?", stale/uncalibrated estimate). Record
# problems are attached to the scenario/issue that carries them; register-level
# problems are returned in the flat list so the CLI can print them.
# ===========================================================================


def validate_graph(graph, config: Config) -> list[Issue]:
    """Validate the assembled graph in place; return every problem found.

    Scenario- and issue-level problems are also attached to the record (so the
    engine can honour trust/error handling later); domain/named-risk/control/
    policy/evidence/KRI/horizon problems are register-level and returned here.
    """
    from .graph import Graph  # local import avoids a load-time cycle

    assert isinstance(graph, Graph)
    problems: list[Issue] = []

    # -- Enterprise anchor --------------------------------------------------
    ent = graph.enterprise
    if ent is None:
        problems.append(Issue("enterprise_missing", ERROR, STRUCTURAL,
                              "enterprise.yaml is missing — no appetite/capacity anchor"))
    else:
        for fld, val in (
            ("revenue_annual", ent.revenue_annual),
            ("capacity_materiality", ent.capacity_materiality),
            ("appetite_pct_of_revenue", ent.appetite_pct_of_revenue),
        ):
            if val is None or val <= 0:
                problems.append(Issue("enterprise_field_invalid", ERROR, STRUCTURAL,
                                      f"enterprise.yaml: {fld} must be a positive number"))
        if ent.declared_appetite is not None and ent.capacity_materiality is not None:
            if ent.declared_appetite > ent.capacity_materiality:
                problems.append(Issue("appetite_above_capacity", FLAG, ACTION,
                                      "enterprise.yaml: declared appetite exceeds capacity/materiality "
                                      "— appetite should sit beneath the hard line (SPEC §4)"))

    # Enterprise lines the individual thresholds are checked against (SPEC v2.1 §D1).
    capacity = ent.capacity_materiality if ent else None
    declared_appetite = ent.declared_appetite if ent else None

    # -- Named risk -> Domain (tree) ---------------------------------------
    for nid, nr in graph.named_risks.items():
        if not nr.domain:
            problems.append(Issue("named_risk_no_domain", ERROR, STRUCTURAL,
                                  f"{nid}: named risk names no domain"))
        elif nr.domain not in graph.domains:
            problems.append(Issue("named_risk_domain_unknown", ERROR, STRUCTURAL,
                                  f"{nid}: domain {nr.domain!r} is not in domains.yaml"))
        if nr.appetite_threshold is None or nr.appetite_threshold <= 0:
            problems.append(Issue("named_risk_appetite_invalid", ERROR, STRUCTURAL,
                                  f"{nid}: appetite_threshold must be a positive number"))
        elif capacity is not None:
            # A single risk may not be permitted to breach the whole company's
            # hard line, and consuming a quarter of it is implausible-but-allowed.
            if nr.appetite_threshold > capacity:
                problems.append(Issue("named_risk_threshold_over_capacity", ERROR, STRUCTURAL,
                                      f"{nid}: appetite_threshold {nr.appetite_threshold:.0f} exceeds "
                                      f"enterprise capacity {capacity:.0f} -- no single risk may be "
                                      f"permitted to breach the company's hard line (SPEC v2.1 §D1)"))
            elif nr.appetite_threshold > 0.25 * capacity:
                problems.append(Issue("named_risk_threshold_large", FLAG, ACTION,
                                      f"{nid}: appetite_threshold {nr.appetite_threshold:.0f} is over a "
                                      f"quarter of enterprise capacity {capacity:.0f} -- justify it"))
        for okr_id in nr.threatens_okrs:
            if okr_id not in graph.okrs:
                problems.append(Issue("named_risk_okr_unknown", FLAG, ACTION,
                                      f"{nid}: threatens_okrs names {okr_id!r}, not in okrs.yaml"))

    # Bottom-up thresholds summing above top-down appetite is normal; 24x is not.
    # This flag is the model telling on itself, which is on-thesis (SPEC v2.1 §D1).
    threshold_sum = sum(
        nr.appetite_threshold for nr in graph.named_risks.values()
        if nr.appetite_threshold is not None
    )
    if declared_appetite and threshold_sum > 3 * declared_appetite:
        problems.append(Issue("threshold_sum_far_over_appetite", FLAG, ACTION,
                              f"sum of named-risk thresholds {threshold_sum:.0f} exceeds 3x declared "
                              f"appetite {declared_appetite:.0f} -- bottom-up appetite has drifted far "
                              f"above the top-down line (SPEC v2.1 §D1)"))

    # -- Scenario -> Named risk (tree) + baseline --------------------------
    for sid, sc in graph.scenarios.items():
        if not sc.id:
            problems.append(Issue("scenario_id_missing", ERROR, STRUCTURAL,
                                  f"{sc.path}: scenario has no id"))
        if not sc.named_risk:
            sc.add(Issue("scenario_no_named_risk", ERROR, STRUCTURAL,
                         f"{sid}: scenario names no named_risk"))
        elif sc.named_risk not in graph.named_risks:
            sc.add(Issue("scenario_named_risk_unknown", ERROR, STRUCTURAL,
                         f"{sid}: named_risk {sc.named_risk!r} is not in named_risks.yaml"))
        if sc.lifecycle_state not in LIFECYCLE_STATES:
            sc.add(Issue("scenario_lifecycle_invalid", FLAG, ACTION,
                         f"{sid}: lifecycle_state must be one of {', '.join(LIFECYCLE_STATES)}; "
                         f"got {sc.lifecycle_state!r}"))
        if sc.trajectory and sc.trajectory not in TRAJECTORIES:
            sc.add(Issue("scenario_trajectory_invalid", FLAG, ACTION,
                         f"{sid}: trajectory must be one of {', '.join(TRAJECTORIES)}; got {sc.trajectory!r}"))
        for variable, ci in sc.baseline_by_variable.items():
            if not _valid_ci_for(variable, ci):
                sc.add(Issue("scenario_baseline_invalid", ERROR, STRUCTURAL,
                             f"{sid}: baseline {variable} is not a valid 90% CI: {ci!r}"))
        problems.extend(sc.errors)
        problems.extend(i for i in sc.problems if i.severity == FLAG)

    # -- Issues -> Scenario (m2m; type discriminator) ----------------------
    for issue in graph.issues:
        _validate_issue(issue, graph, config)
        problems.extend(issue.problems)

    # -- Control -> Named risk (m2m) + Control -> Policy (tree) -------------
    for cid, ctrl in graph.controls.items():
        if not ctrl.mapped_named_risks:
            # A control mapping to no risk is flagged "why do we do this?" (SPEC §2.6).
            problems.append(Issue("control_maps_no_risk", FLAG, ACTION,
                                  f"{cid}: control maps to no named risk — why do we do this?"))
        else:
            for nid in ctrl.mapped_named_risks:
                if nid not in graph.named_risks:
                    problems.append(Issue("control_named_risk_unknown", FLAG, ACTION,
                                          f"{cid}: mapped_named_risks names {nid!r}, not in named_risks.yaml"))
        if not ctrl.policy:
            problems.append(Issue("control_no_policy", FLAG, ACTION,
                                  f"{cid}: control traces up to no governing policy (SPEC §2.7)"))
        elif ctrl.policy not in graph.policies:
            problems.append(Issue("control_policy_unknown", FLAG, ACTION,
                                  f"{cid}: policy {ctrl.policy!r} is not in policies.yaml"))

    # -- Evidence -> Control (m2m) -----------------------------------------
    for eid, ev in graph.evidence.items():
        if not ev.supports_controls:
            problems.append(Issue("evidence_no_control", FLAG, ACTION,
                                  f"{eid}: evidence supports no control"))
        for cid in ev.supports_controls:
            if cid not in graph.controls:
                problems.append(Issue("evidence_control_unknown", FLAG, ACTION,
                                      f"{eid}: supports_controls names {cid!r}, not in controls.yaml"))

    # -- KRI -> Scenario / Named risk (informs) ----------------------------
    for kid, kri in graph.kris.items():
        if not kri.informs:
            problems.append(Issue("kri_informs_nothing", FLAG, ACTION,
                                  f"{kid}: KRI informs no scenario or named risk"))
        for target in kri.informs:
            if target not in graph.scenarios and target not in graph.named_risks:
                problems.append(Issue("kri_target_unknown", FLAG, ACTION,
                                      f"{kid}: informs {target!r}, not a known scenario or named risk"))

    # -- Horizon: names BOTH a candidate domain AND a watched KRI ----------
    for hid, hz in graph.horizon.items():
        if not hz.candidate_domain or not hz.watched_kri:
            problems.append(Issue("horizon_incomplete", ERROR, STRUCTURAL,
                                  f"{hid}: a horizon item must name both a candidate_domain and a "
                                  f"watched_kri (SPEC §2.10); a news alert is not a tracked risk"))
        else:
            if hz.candidate_domain not in graph.domains:
                problems.append(Issue("horizon_domain_unknown", FLAG, ACTION,
                                      f"{hid}: candidate_domain {hz.candidate_domain!r} is not in domains.yaml"))
            if hz.watched_kri not in graph.kris:
                problems.append(Issue("horizon_kri_unknown", FLAG, ACTION,
                                      f"{hid}: watched_kri {hz.watched_kri!r} is not in kris.yaml"))

    return problems


def _validate_issue(issue, graph, config: Config) -> None:
    """Structural + trust gates for one generalised issue record (SPEC §2.5)."""
    if not issue.id:
        issue.add(Issue("issue_id_missing", ERROR, STRUCTURAL, f"{issue.path}: missing id"))

    if issue.type not in ISSUE_TYPES:
        issue.add(Issue("issue_type_invalid", ERROR, STRUCTURAL,
                        f"{issue.id}: type must be one of {', '.join(ISSUE_TYPES)}; got {issue.type!r}"))
        return  # can't sensibly validate the rest without a known type

    # Every issue must map to >= 1 scenario (SPEC §10 Day-1 invariant).
    resolved = graph.resolved_scenarios(issue)
    if not resolved:
        issue.add(Issue("issue_no_scenario", ERROR, STRUCTURAL,
                        f"{issue.id}: maps to no scenario (needs mapped_scenarios or a bridged mapped_risk)"))
    else:
        for sid in resolved:
            if sid not in graph.scenarios:
                issue.add(Issue("issue_scenario_unknown", ERROR, STRUCTURAL,
                                f"{issue.id}: mapped scenario {sid!r} is not in scenarios/"))

    # Factor-moving issues (exception, vuln) must carry a valid moved factor.
    if issue.type in FACTOR_MOVING_ISSUE_TYPES:
        if issue.moves not in VARIABLES:
            issue.add(Issue("issue_moves_invalid", ERROR, STRUCTURAL,
                            f"{issue.id}: moves must be one of {', '.join(VARIABLES)}; got {issue.moves!r}"))
        elif issue.with_ci_90ci is None:
            field_name = "with_acceptance_90ci" if issue.type == ISSUE_VULN else "with_exception_90ci"
            issue.add(Issue("issue_band_point_estimate", ERROR, STRUCTURAL,
                            f"{issue.id}: {field_name} must be a [low, high] 90% CI, not a point estimate"))
        elif not _valid_ci_for(issue.moves, issue.with_ci_90ci):
            issue.add(Issue("issue_band_out_of_range", ERROR, STRUCTURAL,
                            f"{issue.id}: accepted band {issue.with_ci_90ci!r} is not valid for {issue.moves}"))
        else:
            _validate_dominance(issue, graph)
        _validate_estimator(issue, graph, config)

    # A finding is not simulated; it carries a bounded severity + a source.
    if issue.type == ISSUE_FINDING:
        if issue.severity not in FINDING_SEVERITIES:
            issue.add(Issue("finding_severity_invalid", ERROR, STRUCTURAL,
                            f"{issue.id}: finding severity must be one of {', '.join(FINDING_SEVERITIES)}; "
                            f"got {issue.severity!r}"))
        if issue.source and issue.source not in FINDING_SOURCES:
            issue.add(Issue("finding_source_invalid", FLAG, ACTION,
                            f"{issue.id}: finding source {issue.source!r} is not one of "
                            f"{', '.join(FINDING_SOURCES)}"))


# Below this share of the baseline geomean on the moved factor, a factor-moving
# issue's effect is materially indistinguishable from the baseline -- a no-op
# (SPEC v2.3 §B2). An exception with no effect is noise on the register.
_NOOP_EFFECT_SHARE = 0.03


def _geomean(ci: list[float]) -> float:
    return (ci[0] * ci[1]) ** 0.5


def _validate_dominance(issue, graph) -> None:
    """An exception/vuln is the removal or weakening of a control, so it can only
    make the moved factor WORSE (SPEC v2.3 §B1). Assert that its ``with_*`` band
    dominates its primary scenario's baseline on the moved factor -- the engine
    cannot infer this semantics; the model has to state it. Also flags a no-op."""
    resolved = graph.resolved_scenarios(issue)
    if not resolved or resolved[0] not in graph.scenarios:
        return  # already errored elsewhere
    scn = graph.scenarios[resolved[0]]
    base = scn.baseline_by_variable.get(issue.moves)
    if base is None:
        return  # malformed baseline already errored on the scenario
    with_ci = issue.with_ci_90ci
    dominates = with_ci[0] >= base[0] and with_ci[1] >= base[1] and (
        with_ci[0] > base[0] or with_ci[1] > base[1]
    )
    if not dominates:
        issue.add(Issue(
            "issue_not_dominant", ERROR, STRUCTURAL,
            f"{issue.id}: with-band {with_ci!r} does not dominate scenario "
            f"{scn.id} baseline {base!r} on {issue.moves} -- an exception weakens a "
            f"control, so it cannot IMPROVE the factor it degrades (SPEC v2.3 §B1)"))
        return
    # Dominant but negligible: a no-op that only adds noise to the register.
    if _geomean(with_ci) / _geomean(base) - 1.0 < _NOOP_EFFECT_SHARE:
        issue.add(Issue(
            "issue_noop_effect", FLAG, ACTION,
            f"{issue.id}: with-band {with_ci!r} is materially indistinguishable from "
            f"scenario {scn.id} baseline {base!r} on {issue.moves} -- an exception with "
            f"no effect is noise on the register (SPEC v2.3 §B2)"))
