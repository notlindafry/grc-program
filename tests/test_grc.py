"""Tests for the GRC-tab derivation layer and render (v4.0 Spec 1).

Two contracts under test:

1. **Isolation (P.4).** The GRC registers and the deviations directory are
   invisible to the eng build: the eng dashboard renders byte-identically
   whether the corpus was loaded through ``load_graph`` or ``load_grc_graph``,
   and no deviation record ever appears on the issues floor.
2. **The derivations.** Each §1.B figure catches exactly the deliberate holes
   seeded in §0.H, names its denominator, and stays diagnostic (the overlay
   never touches the eng portfolio).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_ledger import dashboard
from risk_ledger.config import Config
from risk_ledger.graph_engine import GraphEngine
from risk_ledger.grc import GRCEngine, load_grc_graph
from risk_ledger.loader import load_graph
from risk_ledger.render_grc import build_grc_page
from risk_ledger.validation import validate_graph

DATA = Path(__file__).resolve().parent.parent / "data"
AS_OF = dt.date(2026, 6, 18)


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config(as_of=AS_OF)


@pytest.fixture(scope="module")
def grc(cfg) -> GRCEngine:
    return GRCEngine(load_grc_graph(DATA), cfg)


# ---------------------------------------------------------------------------
# Isolation (P.4)
# ---------------------------------------------------------------------------


def test_eng_dashboard_byte_identical_under_grc_loader(cfg):
    g_eng = load_graph(DATA)
    validate_graph(g_eng, cfg)
    page_eng = dashboard.build_dashboard(g_eng, GraphEngine(g_eng, cfg))

    g_grc = load_grc_graph(DATA)
    validate_graph(g_grc, cfg)
    page_via_grc = dashboard.build_dashboard(g_grc, GraphEngine(g_grc, cfg))

    assert page_eng == page_via_grc  # the loader extension is invisible to eng


def test_deviations_never_on_the_issues_floor(grc):
    issue_ids = {i.id for i in grc.graph.issues}
    assert not any(i.startswith("DEV-") for i in issue_ids)
    assert len(grc.graph.deviations) == 5
    # And the deviations are exactly the guardrail_events/ records.
    assert all(d.id.startswith("DEV-") for d in grc.graph.deviations)


def test_registers_loaded(grc):
    g = grc.graph
    assert g.load_errors == []
    assert len(g.regulations) == 8  # 5 DORA pillars + 3 PCI requirements
    assert len(g.guardrails) == 4
    assert len(g.agents) == 5
    assert g.sla.policy_review_cadence_months == 12


# ---------------------------------------------------------------------------
# Governance derivations
# ---------------------------------------------------------------------------


def test_policy_currency_catches_the_seeded_overdue(grc):
    pc = grc.policy_currency()
    assert pc.total == 18  # includes POL-AI-USE
    overdue = {o.policy_id for o in pc.overdue}
    assert overdue == {"POL-PHYSICAL", "POL-HR-SECURITY", "POL-ASSET-MGMT"}
    assert all(o.days_overdue > 0 for o in pc.overdue)


def test_guardrail_coverage_names_the_ungoverned_agent(grc):
    ac = grc.agent_coverage()
    assert len(ac.detected) == 5
    assert ac.uncovered == ["agent:data-migration-bot"]
    assert ac.governed_undetected == []  # every governed agent is also detected


def test_requirement_coverage_and_two_direction_consistency(grc):
    rc = grc.requirement_coverage()
    assert rc.total == 8 and len(rc.satisfied) == 8
    assert rc.unknown_control_refs == []  # every satisfied_by id exists
    assert rc.mismatched_framework_refs == []  # controls agree with regulations


# ---------------------------------------------------------------------------
# Risk derivations
# ---------------------------------------------------------------------------


def test_unscored_risk_is_the_deliberate_hole(grc):
    assert grc.unscored_risks() == ["NR-AI-DISCLOSURE"]


def test_risk_hygiene_attributes_flags(grc):
    rh = grc.risk_hygiene()
    assert rh.total == 25
    # The two estimator trust flags in the corpus land on their risks.
    assert "NR-VENDOR-ACCESS" in rh.flagged
    assert "NR-ENDPOINT-MALWARE" in rh.flagged
    assert len(rh.passing) == rh.total - len(rh.flagged)


def test_remediation_sla_is_a_process_lens(grc):
    rs = grc.remediation_sla()
    assert rs.total_live == 40
    assert all(r.target_date < AS_OF for r in rs.overdue)
    assert all(i.renewal_count >= grc.config.renewal_alert_count for i in rs.kicked)


# ---------------------------------------------------------------------------
# Compliance derivations
# ---------------------------------------------------------------------------


def test_unmapped_controls_two_separate_denominators(grc):
    no_policy, no_risk = grc.unmapped_controls()
    assert no_policy == []  # zero by construction
    assert len(no_risk) == 38  # the illustration's genuinely unexercised controls


def test_findings_without_plan(grc):
    assert {i.id for i in grc.findings_without_plan()} == {"FND-2026-0005", "FND-2026-0006"}


def test_cross_framework_reuse_catches_the_shared_controls(grc):
    reuse = grc.cross_framework_reuse()
    assert "A.8.15" in reuse  # DORA-P2 + PCI-REQ-10 (the seeded share)
    assert "A.8.8" in reuse   # DORA-P1 + DORA-P3 + PCI-REQ-11
    assert all(len(rids) > 1 for rids in reuse.values())


def test_over_engineered_controls_all_below_appetite(grc):
    states = {r.named_risk.id: r.state for r in grc.eng.all_named_risk_residuals()}
    for cid, nids in grc.over_engineered_controls():
        assert nids and all(states[n] == "below" for n in nids)


# ---------------------------------------------------------------------------
# AI governance (§1.C overlay included)
# ---------------------------------------------------------------------------


def test_deviation_sla_reads(grc):
    by_id = {s.dev.id: s for s in grc.deviation_sla()}
    assert by_id["DEV-2026-0001"].met is False and by_id["DEV-2026-0001"].days_overdue == 2
    assert by_id["DEV-2026-0002"].met is True
    assert by_id["DEV-2026-0005"].met is None  # open, inside its window


def test_provisional_overlay_contributes_only_proposed_and_accepted(grc):
    pe = grc.provisional_exposure()
    ids = {c.dev.id for c in pe.contributions}
    assert ids == {"DEV-2026-0001", "DEV-2026-0002", "DEV-2026-0005"}
    for c in pe.contributions:
        assert c.band.mean > 0  # a deviation adds provisional exposure, never removes
        rail = grc.graph.guardrails[c.dev.guardrail]
        lo, hi = c.effective_ci
        assert lo <= rail.max_band_90ci[0] and hi <= rail.max_band_90ci[1]  # bounded


def test_overlay_never_touches_the_eng_portfolio(grc, cfg):
    # The eng portfolio computed over the same extended graph must equal the
    # portfolio over the plain graph: deviations are not a residual input.
    plain = load_graph(DATA)
    validate_graph(plain, cfg)
    p_plain = GraphEngine(plain, cfg).portfolio()
    p_ext = grc.eng.portfolio()
    assert p_ext.band.low == p_plain.band.low
    assert p_ext.band.high == p_plain.band.high
    assert p_ext.p_over_capacity == p_plain.p_over_capacity


def test_ladder_completeness_catches_the_missing_rung(grc):
    complete, incomplete = grc.ladder_completeness()
    assert incomplete == {"GR-AGENT-DATA-EXPORT": ["critical"]}
    assert len(complete) == 3


# ---------------------------------------------------------------------------
# Render (§1.D–§1.F)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def page(grc) -> str:
    return build_grc_page(grc)


def test_page_shell_and_wip(page):
    assert page.startswith("<!doctype html>")
    assert 'name="robots" content="noindex, nofollow"' in page
    assert "WORK IN PROGRESS" in page
    assert 'href="dashboard.html"' in page  # nav to the eng tab


def test_no_composite_score_and_denominators(page):
    assert "no blended health score" in page
    # The two unmapped-control figures are reported separately, never one number.
    assert "governing <i>policy</i>" in page and "no <i>named risk</i>" in page


def test_status_words_never_colour_alone(page):
    # Every status span carries a word; spot the vocabulary the tab uses.
    for word in ("overdue", "on SLA", "uncovered", "over-controlled", "unscored", "fresh"):
        assert word in page
    # Two-sided scale: over-engineered controls read amber via --status-below,
    # and the page never marks over-control green.
    assert "over-controlled" in page


def test_standards_attribution_is_precise(page):
    assert "NIST AI 100-1" in page
    assert "Cloud Security Alliance" in page
    assert "AAGATE" in page
    assert "not NIST-published" in page


def test_provisional_overlay_labeled_provisional(page):
    # The deviation-exposure overlay stays clearly provisional and out of the
    # eng total, and is framed as a modeling choice ("for the purposes of this
    # simulation"), without leaking internal jargon (Model B, provisional_move).
    assert "Provisional exposure" in page
    assert "stays out of the eng portfolio total" in page
    assert "the purposes of this simulation" in page
    assert "Model B" not in page and "provisional_move" not in page


def test_find_the_number_in_two_places(page, grc):
    # §1.G acceptance 4 spot-checks: a policy, a control, a finding, and a
    # named risk each appear consistently where they are shown.
    pc = grc.policy_currency()
    worst = pc.overdue[0]
    assert page.count(worst.policy_id) >= 2  # scorecard worst-aging + governance table
    assert f"{worst.days_overdue}d overdue" in page
    assert page.count("FND-2026-0006") >= 1 and "2 finding(s) with no plan" in page
    assert page.count("DEV-2026-0001") >= 1  # the deviation-review table
    # A named risk carrying provisional exposure names its own id in that table.
    pe = grc.provisional_exposure()
    nid = next(iter(pe.by_risk))
    assert page.count(nid) >= 1
    assert page.count("A.8.15") >= 1  # reuse table
