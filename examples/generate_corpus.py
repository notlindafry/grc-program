#!/usr/bin/env python3
"""Generate the demo corpus under ``data/``.

This is a *development* helper, not part of the tool. It writes a coherent,
deterministic set of YAML records that exercises every path in the ledger and
tells the motivating story from the SPEC: a cloud migration under a hard
deadline that quietly becomes a lift-and-shift while starving three other teams.

The committed YAML files under ``data/`` are the source of truth the ledger
reads; this script just lets us regenerate and re-tune them in one place. Run::

    python examples/generate_corpus.py

The numeric ranges below are the tuning knobs. They are chosen so that:
  * RISK-ACCT-TAKEOVER breaches by *accumulation* (no single exception over alone),
  * RISK-DATA-EXFIL straddles via a *single-acceptance* (EXC-...-0133 dominates),
  * RISK-PLATFORM-OUTAGE breaches via a *single-acceptance* (region concentration,
    EXC-...-0170, dominates) -- the availability-domain parallel to the DLP case,
  * the gcloud-migration external footprint outweighs its internal one,
  * acceptance accelerates into the period_end.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EXC = DATA / "exceptions"

CUTOVER = dt.date(2026, 6, 30)

# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------

RISKS = """\
# The light register. One entry per risk the organization tracks. Holds the
# shared baseline and the numeric appetite so they are not duplicated across
# exceptions and cannot drift. All quantities are 90% confidence intervals.

RISK-ACCT-TAKEOVER:
  title: Account takeover of an internal system via credential compromise
  baseline:
    opportunity_frequency_90ci: [10, 40]           # conditions per year that could produce this loss
    probability_of_realization_90ci: [0.005, 0.02] # given the condition, chance the loss is realized (control failure folded in)
    loss_magnitude_90ci: [2000000, 5000000]        # loss if a loss event occurs, USD
  appetite_threshold: 5000000

RISK-DATA-EXFIL:
  title: Exfiltration of regulated data from an analytics or export path
  baseline:
    opportunity_frequency_90ci: [20, 80]
    probability_of_realization_90ci: [0.01, 0.04]
    loss_magnitude_90ci: [1000000, 3000000]
  appetite_threshold: 6000000

RISK-PAYMENT-FRAUD:
  title: Fraudulent transactions against the payments platform
  baseline:
    opportunity_frequency_90ci: [15, 50]
    probability_of_realization_90ci: [0.02, 0.06]
    loss_magnitude_90ci: [1200000, 3000000]
  appetite_threshold: 30000000

RISK-PCI-SCOPE:
  title: PCI scope expansion / cardholder data handling gap
  baseline:
    opportunity_frequency_90ci: [5, 20]
    probability_of_realization_90ci: [0.01, 0.04]
    loss_magnitude_90ci: [2000000, 7000000]
  appetite_threshold: 25000000

RISK-DATA-QUALITY:
  title: Corrupted or unvalidated data feeding downstream decisions
  baseline:
    opportunity_frequency_90ci: [10, 50]
    probability_of_realization_90ci: [0.02, 0.10]
    loss_magnitude_90ci: [500000, 2000000]
  appetite_threshold: 15000000

RISK-DATA-AVAILABILITY:
  title: Loss of availability of a core data platform service
  baseline:
    opportunity_frequency_90ci: [10, 40]
    probability_of_realization_90ci: [0.02, 0.08]
    loss_magnitude_90ci: [800000, 2500000]
  appetite_threshold: 15000000

RISK-ABUSE-ESCALATION:
  title: Unmitigated abuse escalating on the platform
  baseline:
    opportunity_frequency_90ci: [20, 80]
    probability_of_realization_90ci: [0.03, 0.10]
    loss_magnitude_90ci: [400000, 1500000]
  appetite_threshold: 15000000

RISK-ABUSE-DETECTION:
  title: Gaps in automated detection of policy-violating content
  baseline:
    opportunity_frequency_90ci: [20, 70]
    probability_of_realization_90ci: [0.02, 0.08]
    loss_magnitude_90ci: [500000, 1800000]
  appetite_threshold: 15000000

RISK-MIGRATION-AVAILABILITY:
  title: Availability regressions introduced by the migration
  baseline:
    opportunity_frequency_90ci: [10, 40]
    probability_of_realization_90ci: [0.02, 0.08]
    loss_magnitude_90ci: [600000, 2000000]
  appetite_threshold: 10000000

RISK-MIGRATION-DATAINTEGRITY:
  title: Data integrity loss during monolith-to-microservices cutover
  baseline:
    opportunity_frequency_90ci: [5, 20]
    probability_of_realization_90ci: [0.01, 0.05]
    loss_magnitude_90ci: [1000000, 4000000]
  appetite_threshold: 10000000

RISK-VENDOR-ACCESS:
  title: Excessive third-party vendor access to internal systems
  baseline:
    opportunity_frequency_90ci: [5, 20]
    probability_of_realization_90ci: [0.01, 0.04]
    loss_magnitude_90ci: [800000, 3000000]
  appetite_threshold: 8000000

RISK-ENDPOINT-MALWARE:
  title: Malware on a corporate endpoint leading to lateral movement
  baseline:
    opportunity_frequency_90ci: [30, 100]
    probability_of_realization_90ci: [0.02, 0.08]
    loss_magnitude_90ci: [300000, 1200000]
  appetite_threshold: 10000000

RISK-PLATFORM-OUTAGE:
  title: Customer-facing outage of a core platform service
  baseline:
    opportunity_frequency_90ci: [20, 60]            # disruptions per year that could cause an outage
    probability_of_realization_90ci: [0.01, 0.04]   # given a disruption, chance it becomes a customer outage (resilient baseline)
    loss_magnitude_90ci: [1500000, 8000000]         # revenue, SLA credits, reputational loss per outage
  appetite_threshold: 15000000

# Material exposure near its appetite, with NO exceptions mapped to it -- the case
# the exception lens alone would miss. A funded strengthen (REM-2026-0005) buys it
# down; it is within appetite today, so it does not add a current breach.
RISK-DATA-RESIDENCY:
  title: Regulated data leaving its required residency region
  baseline:
    opportunity_frequency_90ci: [10, 18]            # cross-region data flows per year that could breach residency
    probability_of_realization_90ci: [0.06, 0.11]   # given a flow, chance it lands non-compliant
    loss_magnitude_90ci: [5000000, 9000000]         # regulatory penalty, remediation, reputational loss
  appetite_threshold: 14000000
"""

ESTIMATORS = """\
# The calibration gate. Each estimate records who made it; the tool checks that
# person here. An estimate from someone uncalibrated, or whose calibration is
# older than the configured refresh window, is flagged and not trusted.

r.chen@company.com:
  calibrated: true
  calibrated_on: 2026-03-15
j.okafor@company.com:
  calibrated: true
  calibrated_on: 2025-11-20
p.nguyen@company.com:
  calibrated: true
  calibrated_on: 2026-01-10
a.silva@company.com:
  calibrated: true
  calibrated_on: 2025-09-05
m.haddad@company.com:
  calibrated: true
  calibrated_on: 2026-02-01

# Uncalibrated: any estimate from here is flagged low-confidence.
t.brooks@company.com:
  calibrated: false

# Stale: calibrated once, but longer ago than the refresh window (365d).
l.romano@company.com:
  calibrated: true
  calibrated_on: 2024-02-01
"""

OKRS = """\
# OKRs the exceptions attach to. An OKR is an Objective plus Key Results. The
# drift view's headline names the objective and displays the key results as the
# commitments the exception footprint is eroding. period_end lets the trajectory
# analysis measure the run-up to a real deadline.

gcloud-migration:
  title: gcloud-migration
  objective: a quality rebuild from monolith to microservices
  key_results:
    - all services decomposed and hardened by cutover
    - maintain 99.9% availability through and after cutover
    - zero critical security findings at cutover
  period_end: 2026-06-30

payments-launch:
  title: payments-launch
  objective: launch the new payments platform to general availability
  key_results:
    - pass the external PCI assessment before launch
    - fraud loss rate under target at GA
  period_end: 2026-07-31

data-platform:
  title: data-platform
  objective: a governed, reliable central data platform
  key_results:
    - DLP enforced on every export path
    - 99.9% pipeline availability
  period_end: 2026-09-30

trust-and-safety:
  title: trust-and-safety
  objective: keep abuse and policy-violating content off the platform
  key_results:
    - abuse-escalation SLA met
    - detection-model recall above target
  period_end: 2026-09-30

mobile-app:
  title: mobile-app
  objective: ship the redesigned mobile application
  key_results:
    - redesigned app in general availability
    - crash-free sessions above target
  period_end: 2026-08-31

internal-tools:
  title: internal-tools
  objective: modernize internal developer and operations tooling
  key_results:
    - legacy toolchain decommissioned
    - TLS 1.3 enforced across internal tools
  period_end: 2026-10-31

core-platform:
  title: core-platform
  objective: keep the core platform reliable and available
  key_results:
    - 99.9% availability across core services
    - quarterly DR test passing
  period_end: 2026-12-31

run-the-business:
  title: run-the-business
  objective: maintain core operations otherwise not associated with a strategic objective
  # the non-strategic catch-all: no key results, and ongoing (no period_end)
"""

CONFIG = """\
# Optional run configuration. CLI flags override these.
monte_carlo:
  iterations: 10000
  seed: 20260617
calibration:
  refresh_window_days: 365
drift:
  final_stretch_weeks: 8
breach:
  # Lead-contributor share of contributed exposure at/above which a breach is
  # classified single-acceptance rather than accumulation. (A contributor that
  # breaches appetite alone is single-acceptance regardless of this number.)
  single_acceptance_share: 0.5
renewals:
  # An active exception renewed at least this many times with its justification
  # never revisited is flagged "temporary forever" in the Persistence view.
  alert_count: 3
# Fiscal-year boundary for the 2026 exposure arc: exceptions filed before this
# date are the book entering the year.
year_start: 2026-01-01
"""


# ---------------------------------------------------------------------------
# Exception writer
# ---------------------------------------------------------------------------


def write_exception(
    eid,
    *,
    title,
    owner,
    filed_on,
    okr,
    control,
    mapped_risk,
    moves,
    with_ci,
    estimated_by,
    estimated_on,
    reason,
    diverted_to=None,
    scope_type="enumerated",
    assets=None,
    population=None,
    target_date="2026-09-01",
    mechanism="enforce_sso_via_idp",
    reduces=None,
    status="active",
    expires_on="2026-09-01",
    renewals=0,
    justification_changed_last=None,
    non_plan=False,
):
    reduces = reduces or moves
    lines = [
        f"id: {eid}",
        f"title: {title}",
        f"owner: {owner}",
        f"filed_on: {filed_on}",
        "",
        f"okr: {okr}",
        f"control: {control}",
        f"mapped_risk: {mapped_risk}",
        "",
        "exception_effect:",
        f"  moves: {moves}",
        f"  with_exception_90ci: [{with_ci[0]}, {with_ci[1]}]",
        f"  estimated_by: {estimated_by}",
        f"  estimated_on: {estimated_on}",
        "",
        f"reason: {reason}",
    ]
    if reason == "resource_reallocation" and diverted_to:
        lines += ["reason_detail:", f"  diverted_to: {diverted_to}"]
    lines += ["scope:", f"  type: {scope_type}"]
    if scope_type == "enumerated":
        rendered = ", ".join(assets or [])
        lines.append(f"  assets: [{rendered}]")
    else:
        lines.append(f"  population: {population}")
    lines.append("remediation:")
    if non_plan:
        lines.append("  # NON-PLAN: no target_date and no mechanism -- will be sent back.")
        lines.append(f"  reduces: {reduces}")
    else:
        lines += [
            f"  target_date: {target_date}",
            f"  mechanism: {mechanism}",
            f"  reduces: {reduces}",
        ]
    lines += [
        f"status: {status}",
        f"expires_on: {expires_on}",
        "renewals:",
        f"  count: {renewals}",
        f"  justification_changed_last: {justification_changed_last if justification_changed_last else 'null'}",
        "",
    ]
    (EXC / f"{eid}.yaml").write_text("\n".join(lines))


REM = DATA / "remediations"


def write_remediation(
    rid,
    *,
    title,
    rtype,
    status,
    owner,
    mechanism,
    target_date,
    restores_control=None,
    mapped_risk=None,
    moves=None,
    post_control_90ci=None,
    estimated_by=None,
    estimated_on=None,
):
    lines = [
        f"id: {rid}",
        f"title: {title}",
        f"type: {rtype}",
        f"status: {status}",
        f"target_date: {target_date}",
        f"owner: {owner}",
        f"mechanism: {mechanism}",
    ]
    if rtype == "restore":
        lines.append(f"restores_control: {restores_control}")
    else:  # strengthen
        lines += [
            f"mapped_risk: {mapped_risk}",
            f"moves: {moves}",
            f"post_control_90ci: [{post_control_90ci[0]}, {post_control_90ci[1]}]",
            f"estimated_by: {estimated_by}",
            f"estimated_on: {estimated_on}",
        ]
    lines.append("")
    (REM / f"{rid}.yaml").write_text("\n".join(lines))


# Date pools for the gcloud-migration trajectory: a handful early, a flood late.
EARLY = [
    dt.date(2026, 1, 12),
    dt.date(2026, 2, 3),
    dt.date(2026, 2, 18),
    dt.date(2026, 3, 5),
    dt.date(2026, 3, 19),
    dt.date(2026, 3, 27),
]
LATE = [dt.date(2026, 5, 6) + dt.timedelta(days=int(i * 1.5)) for i in range(27)]


def build() -> None:
    DATA.mkdir(exist_ok=True)
    EXC.mkdir(exist_ok=True)
    REM.mkdir(exist_ok=True)
    for old in REM.glob("*.yaml"):
        old.unlink()
    for old in EXC.glob("*.yaml"):
        old.unlink()

    (DATA / "risks.yaml").write_text(RISKS)
    (DATA / "estimators.yaml").write_text(ESTIMATORS)
    (DATA / "okrs.yaml").write_text(OKRS)
    (DATA / "config.yaml").write_text(CONFIG)

    migration_dates = iter(EARLY + LATE)  # 33 dates: 6 early, 27 late
    cal = ["r.chen@company.com", "j.okafor@company.com", "p.nguyen@company.com",
           "a.silva@company.com", "m.haddad@company.com"]

    PLATFORM = "platform-lead@company.com"
    IAM = "iam-lead@company.com"
    DATAPLAT = "data-platform-lead@company.com"

    # --- gcloud-migration internal: 12 legacy-auth on ACCT-TAKEOVER ---------
    legacy = [
        ("EXC-2026-0142", "Skip MFA on internal analytics console to hit migration cutover",
         [0.012, 0.035], ["analytics-console-prod"], "enforce_sso_via_idp", False),
        ("EXC-2026-0118", "Relax session timeout on legacy admin portal during cutover",
         [0.012, 0.030], ["legacy-admin-portal"], "shorten_session_ttl_via_idp", False),
        ("EXC-2026-0119", "Defer MFA rollout on internal wiki during migration",
         [0.010, 0.030], ["internal-wiki"], "enforce_sso_via_idp", False),
        ("EXC-2026-0120", "Allow shared break-glass account on legacy jobs runner",
         [0.012, 0.034], ["legacy-jobs-runner"], "remove_shared_accounts", False),
        ("EXC-2026-0121", "Skip MFA on internal metrics dashboard for cutover window",
         [0.010, 0.028], ["metrics-dashboard"], "enforce_sso_via_idp", False),
        ("EXC-2026-0122", "Keep password-only auth on legacy build server",
         [0.012, 0.032], ["legacy-build-server"], "enforce_sso_via_idp", False),
        ("EXC-2026-0123", "Defer MFA on internal feature-flag console",
         [0.011, 0.030], ["feature-flag-console"], "enforce_sso_via_idp", False),
        ("EXC-2026-0124", "Allow legacy API keys on internal data browser",
         [0.012, 0.033], ["internal-data-browser"], "rotate_to_scoped_tokens", False),
        # 4 non-plan (no remediation target/mechanism) -- sent back.
        ("EXC-2026-0125", "Skip MFA on legacy reporting console (cutover)",
         [0.011, 0.031], ["legacy-reporting-console"], "enforce_sso_via_idp", True),
        ("EXC-2026-0126", "Relax auth on internal scheduler UI (cutover)",
         [0.010, 0.029], ["internal-scheduler-ui"], "enforce_sso_via_idp", True),
        ("EXC-2026-0127", "Defer MFA on legacy ops console (cutover)",
         [0.012, 0.032], ["legacy-ops-console"], "enforce_sso_via_idp", True),
        ("EXC-2026-0128", "Keep shared admin login on legacy queue manager (cutover)",
         [0.011, 0.030], ["legacy-queue-manager"], "remove_shared_accounts", True),
    ]
    # EXC-...-0122 has been renewed unchanged -> it surfaces in the Persistence
    # view. Its filed_on stays on the migration timeline (set by next()).
    legacy_renewals = {"EXC-2026-0122": 3}
    for i, (eid, title, ci, assets, mech, non_plan) in enumerate(legacy):
        write_exception(
            eid, title=title, owner=PLATFORM, filed_on=next(migration_dates),
            okr="gcloud-migration", control="IAM-LEGACY-AUTH-001",
            mapped_risk="RISK-ACCT-TAKEOVER", moves="probability_of_realization",
            with_ci=ci, estimated_by=cal[i % len(cal)], estimated_on="2026-04-15",
            reason="timeline" if i % 3 else "technical_constraint",
            assets=assets, mechanism=mech, non_plan=non_plan,
            renewals=legacy_renewals.get(eid, 0),
        )

    # --- service-account sprawl (its own control) on ACCT-TAKEOVER ----------
    write_exception(
        "EXC-2026-0151", title="Service-account sprawl on migrated workloads",
        owner=IAM, filed_on=next(migration_dates), okr="gcloud-migration",
        control="IAM-SVCACCT-003", mapped_risk="RISK-ACCT-TAKEOVER",
        moves="probability_of_realization", with_ci=[0.011, 0.028],
        estimated_by="r.chen@company.com", estimated_on="2026-05-20",
        reason="timeline", assets=["svcacct-pool-prod"],
        mechanism="rotate_and_scope_service_accounts", target_date="2026-08-15",
    )

    # --- 2 other migration-internal exceptions on migration-owned risks -----
    write_exception(
        "EXC-2026-0160", title="Defer chaos/availability testing on migrated order service",
        owner=PLATFORM, filed_on=next(migration_dates), okr="gcloud-migration",
        control="REL-AVAIL-010", mapped_risk="RISK-MIGRATION-AVAILABILITY",
        moves="probability_of_realization", with_ci=[0.05, 0.14],
        estimated_by="j.okafor@company.com", estimated_on="2026-05-22",
        reason="timeline", assets=["order-service"], mechanism="add_chaos_suite",
    )
    write_exception(
        "EXC-2026-0161", title="Skip dual-write verification during inventory cutover",
        owner=PLATFORM, filed_on=next(migration_dates), okr="gcloud-migration",
        control="DATA-INTEG-004", mapped_risk="RISK-MIGRATION-DATAINTEGRITY",
        moves="probability_of_realization", with_ci=[0.03, 0.10],
        estimated_by="p.nguyen@company.com", estimated_on="2026-05-25",
        reason="technical_constraint", assets=["inventory-service"],
        mechanism="enable_dual_write_checks",
    )

    # --- DLP cluster on DATA-EXFIL (data-platform's own decisions) -----------
    write_exception(
        "EXC-2026-0133", title="DLP disabled on the analytics export path",
        owner=DATAPLAT, filed_on=dt.date(2026, 4, 28), okr="data-platform",
        control="DLP-EXPORT-001", mapped_risk="RISK-DATA-EXFIL",
        moves="loss_magnitude", with_ci=[4000000, 9000000],
        estimated_by="a.silva@company.com", estimated_on="2026-04-28",
        reason="cost", assets=["analytics-export-pipeline"],
        mechanism="re_enable_dlp_with_tuned_rules", reduces="loss_magnitude",
    )
    write_exception(
        "EXC-2026-0134", title="DLP sampling reduced on warehouse export job",
        owner=DATAPLAT, filed_on=dt.date(2026, 5, 2), okr="data-platform",
        control="DLP-EXPORT-001", mapped_risk="RISK-DATA-EXFIL",
        moves="loss_magnitude", with_ci=[1500000, 4000000],
        estimated_by="a.silva@company.com", estimated_on="2026-05-02",
        reason="cost", assets=["warehouse-export-job"],
        mechanism="re_enable_dlp_with_tuned_rules", reduces="loss_magnitude",
    )
    write_exception(
        "EXC-2026-0135", title="DLP disabled on ad-hoc BI export connector",
        owner=DATAPLAT, filed_on=dt.date(2026, 5, 9), okr="data-platform",
        control="DLP-EXPORT-001", mapped_risk="RISK-DATA-EXFIL",
        moves="loss_magnitude", with_ci=[1500000, 3800000],
        estimated_by="m.haddad@company.com", estimated_on="2026-05-09",
        reason="technical_constraint", assets=["bi-export-connector"],
        mechanism="re_enable_dlp_with_tuned_rules", reduces="loss_magnitude",
    )

    # --- External: 18 exceptions diverted_to gcloud-migration ---------------
    def external(eid, title, owner, okr, control, risk, moves, ci, est, mech, reduces=None):
        write_exception(
            eid, title=title, owner=owner, filed_on=next(migration_dates),
            okr=okr, control=control, mapped_risk=risk, moves=moves,
            with_ci=ci, estimated_by=est, estimated_on="2026-05-30",
            reason="resource_reallocation", diverted_to="gcloud-migration",
            assets=[f"{okr}-system"], mechanism=mech, reduces=reduces or moves,
        )

    # payments-launch: 9 (PAYMENT-FRAUD x5, PCI-SCOPE x4)
    for n in range(5):
        external(f"EXC-2026-020{n + 1}", f"Deferred fraud-rule tuning ({n + 1}) — team pulled to migration",
                 "payments-lead@company.com", "payments-launch", "FRAUD-RULES-007",
                 "RISK-PAYMENT-FRAUD", "probability_of_realization", [0.04, 0.09],
                 cal[n % len(cal)], "tune_fraud_rules")
    for n in range(4):
        external(f"EXC-2026-020{n + 6}", f"Deferred PCI segmentation work ({n + 1}) — staff on migration",
                 "payments-lead@company.com", "payments-launch", "PCI-SEG-002",
                 "RISK-PCI-SCOPE", "probability_of_realization", [0.04, 0.10],
                 cal[n % len(cal)], "complete_network_segmentation")
    # data-platform: 6 (DATA-QUALITY x3, DATA-AVAILABILITY x3)
    for n in range(3):
        external(f"EXC-2026-021{n + 1}", f"Deferred data-validation checks ({n + 1}) — engineers on migration",
                 DATAPLAT, "data-platform", "DQ-VALIDATION-005",
                 "RISK-DATA-QUALITY", "probability_of_realization", [0.08, 0.20],
                 cal[n % len(cal)], "restore_validation_suite")
    for n in range(3):
        external(f"EXC-2026-021{n + 4}", f"Deferred HA failover testing ({n + 1}) — on-call pulled to migration",
                 DATAPLAT, "data-platform", "REL-HA-009",
                 "RISK-DATA-AVAILABILITY", "probability_of_realization", [0.06, 0.14],
                 cal[n % len(cal)], "schedule_failover_drills")
    # trust-and-safety: 3 (ABUSE-ESCALATION x2, ABUSE-DETECTION x1)
    external("EXC-2026-0221", "Deferred abuse-escalation playbook update — team on migration",
             "tns-lead@company.com", "trust-and-safety", "ABUSE-PLAYBOOK-003",
             "RISK-ABUSE-ESCALATION", "probability_of_realization", [0.05, 0.13],
             "j.okafor@company.com", "refresh_escalation_playbook")
    external("EXC-2026-0222", "Deferred reviewer staffing for abuse queue — staff on migration",
             "tns-lead@company.com", "trust-and-safety", "ABUSE-PLAYBOOK-003",
             "RISK-ABUSE-ESCALATION", "probability_of_realization", [0.05, 0.12],
             "p.nguyen@company.com", "refresh_escalation_playbook")
    external("EXC-2026-0223", "Delayed detection-model retrain — ML team pulled to migration",
             "tns-lead@company.com", "trust-and-safety", "DETECT-MODEL-006",
             "RISK-ABUSE-DETECTION", "probability_of_realization", [0.05, 0.12],
             "a.silva@company.com", "retrain_detection_model")

    # --- Tech Risk: customer-facing platform outage (RISK-PLATFORM-OUTAGE) ---
    # Region concentration is the dominant single-acceptance contributor (a cost
    # decision, internal to the migration); the skipped DR test extends the
    # migration's *external* footprint into the availability domain.
    write_exception(
        "EXC-2026-0170", title="Run core services single-region to cut infrastructure cost",
        owner=PLATFORM, filed_on=dt.date(2026, 4, 20), okr="gcloud-migration",
        control="REL-MULTIREGION-014", mapped_risk="RISK-PLATFORM-OUTAGE",
        moves="probability_of_realization", with_ci=[0.30, 0.58],
        estimated_by="j.okafor@company.com", estimated_on="2026-04-20",
        reason="cost", assets=["core-services-prod"],
        mechanism="deploy_multi_region_active_active", target_date="2026-12-01",
        expires_on="2026-12-01",
    )
    write_exception(
        "EXC-2026-0171", title="Skip quarterly platform DR test to free the team for migration",
        owner=PLATFORM, filed_on=dt.date(2026, 5, 20), okr="core-platform",
        control="REL-DR-TEST-015", mapped_risk="RISK-PLATFORM-OUTAGE",
        moves="probability_of_realization", with_ci=[0.24, 0.50],
        estimated_by="p.nguyen@company.com", estimated_on="2026-05-20",
        reason="resource_reallocation", diverted_to="gcloud-migration",
        assets=["platform-failover"], mechanism="resume_quarterly_dr_tests",
        target_date="2026-09-30", expires_on="2026-09-30",
    )

    # --- Malformed / send-back examples -------------------------------------
    # Uncalibrated estimator -> trust flag.
    write_exception(
        "EXC-2026-0149", title="Allow legacy TLS on internal-tools gateway",
        owner="it-lead@company.com", filed_on=dt.date(2026, 5, 12), okr="internal-tools",
        control="CRYPTO-TLS-008", mapped_risk="RISK-ENDPOINT-MALWARE",
        moves="probability_of_realization", with_ci=[0.05, 0.15],
        estimated_by="t.brooks@company.com", estimated_on="2026-05-12",
        reason="technical_constraint", assets=["internal-tools-gateway"],
        mechanism="enforce_tls13",
    )
    # resource_reallocation with no destination -> action flag.
    write_exception(
        "EXC-2026-0140", title="Deferred PCI logging review (resources reallocated, destination unstated)",
        owner="payments-lead@company.com", filed_on=dt.date(2026, 5, 1), okr="payments-launch",
        control="PCI-LOG-011", mapped_risk="RISK-PCI-SCOPE",
        moves="probability_of_realization", with_ci=[0.03, 0.10],
        estimated_by="m.haddad@company.com", estimated_on="2026-05-01",
        reason="resource_reallocation", diverted_to=None,
        assets=["pci-logging-pipeline"], mechanism="restore_log_review",
    )
    # 2 stale-estimator exceptions -> trust flag (excluded from bands).
    write_exception(
        "EXC-2026-0301", title="Broad vendor VPN access retained on mobile build farm",
        owner="mobile-lead@company.com", filed_on=dt.date(2026, 4, 10), okr="mobile-app",
        control="VENDOR-ACCESS-012", mapped_risk="RISK-VENDOR-ACCESS",
        moves="probability_of_realization", with_ci=[0.03, 0.09],
        estimated_by="l.romano@company.com", estimated_on="2026-04-10",
        reason="cost", assets=["mobile-build-farm"], mechanism="scope_vendor_access",
    )
    write_exception(
        "EXC-2026-0302", title="Defer endpoint EDR upgrade on mobile team laptops",
        owner="mobile-lead@company.com", filed_on=dt.date(2026, 4, 14), okr="mobile-app",
        control="EDR-COVERAGE-013", mapped_risk="RISK-ENDPOINT-MALWARE",
        moves="probability_of_realization", with_ci=[0.04, 0.10],
        estimated_by="l.romano@company.com", estimated_on="2026-04-14",
        reason="cost", assets=["mobile-team-laptops"], mechanism="deploy_edr_agent",
    )

    # --- 7 clean within-appetite filler exceptions --------------------------
    fillers = [
        ("EXC-2026-0310", "Temporary vendor access for mobile analytics SDK", "mobile-lead@company.com",
         "mobile-app", "VENDOR-ACCESS-012", "RISK-VENDOR-ACCESS", [0.02, 0.06], "scope_vendor_access"),
        ("EXC-2026-0311", "Defer EDR tuning on mobile CI runners", "mobile-lead@company.com",
         "mobile-app", "EDR-COVERAGE-013", "RISK-ENDPOINT-MALWARE", [0.03, 0.08], "deploy_edr_agent"),
        ("EXC-2026-0312", "Allow read-only vendor access to internal dashboards", "mobile-lead@company.com",
         "mobile-app", "VENDOR-ACCESS-012", "RISK-VENDOR-ACCESS", [0.02, 0.05], "scope_vendor_access"),
        ("EXC-2026-0313", "Defer EDR upgrade on internal-tools jump host", "it-lead@company.com",
         "internal-tools", "EDR-COVERAGE-013", "RISK-ENDPOINT-MALWARE", [0.03, 0.07], "deploy_edr_agent"),
        ("EXC-2026-0314", "Temporary vendor SSH to internal-tools sandbox", "it-lead@company.com",
         "internal-tools", "VENDOR-ACCESS-012", "RISK-VENDOR-ACCESS", [0.02, 0.06], "scope_vendor_access"),
        ("EXC-2026-0315", "Deferred PCI doc refresh (own decision, resourced)", "payments-lead@company.com",
         "payments-launch", "PCI-SEG-002", "RISK-PCI-SCOPE", [0.02, 0.06], "complete_network_segmentation"),
        ("EXC-2026-0316", "Defer secondary reviewer on low-severity abuse queue", "tns-lead@company.com",
         "trust-and-safety", "DETECT-MODEL-006", "RISK-ABUSE-DETECTION", [0.03, 0.07], "retrain_detection_model"),
    ]
    # Renewal history for the Persistence view. (count, justification_changed_last)
    # Those renewed >= alert_count (3) unchanged flag as "temporary forever"; 0315
    # was re-examined (justification set) so it does NOT flag; 0311/0316 are
    # renewed-but-below-threshold so they only populate the "renewed once" count.
    renewal_overrides = {
        "EXC-2026-0310": (5, None),
        "EXC-2026-0311": (1, None),
        "EXC-2026-0312": (4, None),
        "EXC-2026-0313": (3, None),
        "EXC-2026-0314": (4, None),
        "EXC-2026-0315": (3, "2026-05-01"),
        "EXC-2026-0316": (2, None),
    }
    # Pull the long-lived ones' filed_on back so the renewal counts are
    # chronologically plausible (an exception renewed 5x was filed years ago).
    filed_overrides = {
        "EXC-2026-0310": dt.date(2024, 6, 3),
        "EXC-2026-0312": dt.date(2024, 11, 18),
        "EXC-2026-0313": dt.date(2025, 1, 20),
        "EXC-2026-0314": dt.date(2025, 3, 9),
        "EXC-2026-0315": dt.date(2024, 9, 14),
    }
    for i, (eid, title, owner, okr, control, risk, ci, mech) in enumerate(fillers):
        count, justification = renewal_overrides.get(eid, (0, None))
        filed_on = filed_overrides.get(eid, dt.date(2026, 3, 1) + dt.timedelta(days=i * 5))
        write_exception(
            eid, title=title, owner=owner, filed_on=filed_on,
            okr=okr, control=control, mapped_risk=risk,
            moves="probability_of_realization", with_ci=ci, estimated_by=cal[i % len(cal)],
            estimated_on="2026-03-10", reason="cost", assets=[f"{okr}-asset-{i}"],
            mechanism=mech, renewals=count, justification_changed_last=justification,
        )

    # --- Remediations: the sign-flipped counterpart of exceptions ------------
    # Three funded restores clear the legacy-auth, DLP, and single-region clusters,
    # returning ACCT-TAKEOVER, DATA-EXFIL, and EXC-0170 to baseline. REM-0004 is
    # only PROPOSED, so EXC-0171 stays and RISK-PLATFORM-OUTAGE remains over after
    # the funded plan -- the intended over-after-remediation demonstration. REM-0005
    # is a funded strengthen on RISK-DATA-RESIDENCY, the register-driven item with
    # no exception behind it.
    write_remediation(
        "REM-2026-0001", title="Enforce SSO via the IdP across legacy consoles",
        rtype="restore", status="funded", owner=PLATFORM,
        mechanism="enforce_sso_via_idp", target_date="2026-09-01",
        restores_control="IAM-LEGACY-AUTH-001",
    )
    write_remediation(
        "REM-2026-0002", title="Re-enable DLP with tuned rules on export paths",
        rtype="restore", status="funded", owner=DATAPLAT,
        mechanism="re_enable_dlp_with_tuned_rules", target_date="2026-09-01",
        restores_control="DLP-EXPORT-001",
    )
    write_remediation(
        "REM-2026-0003", title="Deploy multi-region active-active for core services",
        rtype="restore", status="funded", owner=PLATFORM,
        mechanism="deploy_multi_region_active_active", target_date="2026-12-01",
        restores_control="REL-MULTIREGION-014",
    )
    write_remediation(
        "REM-2026-0004", title="Resume quarterly platform DR tests",
        rtype="restore", status="proposed", owner=PLATFORM,
        mechanism="resume_quarterly_dr_tests", target_date="2026-09-01",
        restores_control="REL-DR-TEST-015",
    )
    write_remediation(
        "REM-2026-0005", title="Implement automated data-residency controls",
        rtype="strengthen", status="funded", owner=DATAPLAT,
        mechanism="implement_automated_data_residency_controls", target_date="2026-10-01",
        mapped_risk="RISK-DATA-RESIDENCY", moves="loss_magnitude",
        post_control_90ci=[1000000, 3000000],
        estimated_by="r.chen@company.com", estimated_on="2026-06-01",
    )

    n = len(list(EXC.glob("*.yaml")))
    r = len(list(REM.glob("*.yaml")))
    print(f"Wrote {n} exception files to {EXC}")
    print(f"Wrote {r} remediation files to {REM}")


if __name__ == "__main__":
    build()
