"""The v2 engine: aggregation, RAG banding, appetite/capacity, control health.

Two layers: unit tests for the pure ``rag_band`` classifier and hand-built
minimal graphs for the invariants (one-path-into-residual, primary-scenario
attribution, emerging held out), and integration tests against the shipped
corpus for the aggregation and the §5 control-health stories.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_ledger.config import Config
from risk_ledger.graph import Graph, assemble_graph
from risk_ledger.graph_engine import (
    GraphEngine,
    RAG_AT,
    RAG_BELOW,
    RAG_OVER,
    rag_band,
)
from risk_ledger.loader import load_graph
from risk_ledger.models import (
    Domain,
    Enterprise,
    Estimator,
    IssueRecord,
    NamedRisk,
    Scenario,
)
from risk_ledger.montecarlo import Band
from risk_ledger.validation import validate_graph

DATA = Path(__file__).resolve().parent.parent / "data"
AS_OF = dt.date(2026, 6, 18)


# ---------------------------------------------------------------------------
# rag_band: the two-sided appetite target (SPEC §4)
# ---------------------------------------------------------------------------


def _band(low, high, mean=None):
    return Band(low=low, high=high, mean=mean if mean is not None else (low + high) / 2)


def test_rag_over_when_whole_band_above_appetite():
    assert rag_band(_band(12, 20), threshold=10) == RAG_OVER


def test_rag_at_when_band_straddles_the_line():
    # A straddle is the truest "at appetite" -> green.
    assert rag_band(_band(8, 14), threshold=10) == RAG_AT


def test_rag_at_in_the_top_quarter_of_tolerance():
    # Fully within but in the top quarter (>= 75% of appetite) -> green.
    assert rag_band(_band(7.6, 9.5, mean=8.5), threshold=10, green_floor=0.75) == RAG_AT


def test_rag_below_with_headroom_is_amber():
    # Deep within appetite: unused tolerance -> amber, not a green all-clear.
    assert rag_band(_band(1, 4, mean=2.5), threshold=10, green_floor=0.75) == RAG_BELOW


# ---------------------------------------------------------------------------
# Minimal hand-built graphs
# ---------------------------------------------------------------------------


def _scn(sid, nr="NR-X", of=(10, 40), por=(0.005, 0.02), lm=(200000, 500000),
         lifecycle="managed", trajectory="stable"):
    return Scenario.parse({
        "id": sid, "named_risk": nr,
        "baseline": {
            "opportunity_frequency_90ci": list(of),
            "probability_of_realization_90ci": list(por),
            "loss_magnitude_90ci": list(lm),
        },
        "lifecycle_state": lifecycle, "trajectory": trajectory,
    }, f"{sid}.yaml")


def _engine(scenarios, issues, *, appetite=5_000_000, capacity=15_000_000,
            named_risks=None, controls=None, evidence=None):
    g = Graph()
    g.enterprise = Enterprise.parse(
        {"revenue_annual": 2e9, "capacity_materiality": capacity, "appetite_pct_of_revenue": 0.005})
    g.domains = {"TR-X": Domain.parse("TR-X", {"title": "X"})}
    g.named_risks = named_risks or {
        "NR-X": NamedRisk.parse("NR-X", {"domain": "TR-X", "appetite_threshold": appetite})
    }
    g.scenarios = {s.id: s for s in scenarios}
    g.issues = issues
    g.controls = controls or {}
    g.evidence = evidence or {}
    g.estimators = {"r.chen@company.com": Estimator.parse(
        "r.chen@company.com", {"calibrated": True, "calibrated_on": "2026-03-15"})}
    assemble_graph(g)
    cfg = Config(iterations=4000, seed=7, as_of=AS_OF)
    validate_graph(g, cfg)  # attach trust flags
    return GraphEngine(g, cfg)


def _exception(eid, scn, moves="probability_of_realization", ci=(0.05, 0.15)):
    return IssueRecord.parse({
        "id": eid, "type": "exception", "mapped_scenarios": [scn],
        "exception_effect": {"moves": moves, "with_exception_90ci": list(ci),
                             "estimated_by": "r.chen@company.com", "estimated_on": "2026-05-01"},
    }, f"{eid}.yaml")


def _finding(fid, scns, severity="high", controls=("A.8.5",)):
    return IssueRecord.parse({
        "id": fid, "type": "finding", "severity": severity, "source": "audit",
        "mapped_scenarios": list(scns), "control": list(controls),
    }, f"{fid}.yaml")


def test_scenario_residual_is_baseline_plus_contribution():
    exc = _exception("EXC-1", "SCN-1", ci=(0.05, 0.15))  # well above baseline PoR
    eng = _engine([_scn("SCN-1")], [exc])
    res = eng.scenario_residual("SCN-1")
    assert [c.issue.id for c in res.contributors] == ["EXC-1"]
    assert res.band.mean > res.baseline.mean  # the exception raised residual


def test_finding_never_enters_the_residual_band():
    # One path into residual (SPEC §4): a finding informs health, never the band.
    exc = _exception("EXC-1", "SCN-1")
    fnd = _finding("FND-1", ["SCN-1"])
    eng_with = _engine([_scn("SCN-1")], [exc, fnd])
    eng_without = _engine([_scn("SCN-1")], [exc])
    res_with = eng_with.scenario_residual("SCN-1")
    res_without = eng_without.scenario_residual("SCN-1")
    # The finding is not a contributor, and the residual is identical.
    assert all(c.issue.type != "finding" for c in res_with.contributors)
    assert res_with.band.mean == pytest.approx(res_without.band.mean)


def test_primary_scenario_attribution():
    # A factor-moving issue mapped to two scenarios contributes only to the first.
    vuln = IssueRecord.parse({
        "id": "VULN-1", "type": "vuln", "mapped_scenarios": ["SCN-1", "SCN-2"],
        "moves": "probability_of_realization", "with_acceptance_90ci": [0.05, 0.15],
        "estimated_by": "r.chen@company.com", "estimated_on": "2026-05-01",
    }, "VULN-1.yaml")
    eng = _engine([_scn("SCN-1"), _scn("SCN-2")], [vuln])
    assert [c.issue.id for c in eng.scenario_residual("SCN-1").contributors] == ["VULN-1"]
    assert eng.scenario_residual("SCN-2").contributors == []


def test_emerging_scenario_held_out_of_named_risk_and_portfolio():
    managed = _scn("SCN-M", nr="NR-X", lifecycle="managed")
    emerging = _scn("SCN-E", nr="NR-X", lifecycle="emerging", trajectory="rising",
                    por=(0.02, 0.30), lm=(500000, 12000000))
    eng = _engine([managed, emerging], [])
    nr = eng.named_risk_residual("NR-X")
    # The named-risk residual is built from the managed scenario only.
    assert nr.scenario_ids == ["SCN-M"]
    # The emerging one is surfaced separately.
    assert [e.scenario.id for e in eng.emerging_items()] == ["SCN-E"]
    # Portfolio excludes emerging: it equals the managed named-risk band.
    assert eng.portfolio().band.mean == pytest.approx(nr.band.mean, rel=0.05)


def test_portfolio_appetite_and_capacity():
    # A big exception pushes the aggregate over both lines.
    exc = _exception("EXC-1", "SCN-1", ci=(0.2, 0.5))
    eng = _engine([_scn("SCN-1", lm=(2000000, 5000000))], [exc],
                  appetite=1_000_000, capacity=2_000_000)
    p = eng.portfolio()
    # The aggregate-over-appetite signal (SPEC §4) is mean-based; the RAG state
    # may read "at" when the wide band straddles a small line.
    assert p.over_appetite is True
    assert p.capacity_breached is True
    assert p.band.mean > p.capacity


# ---------------------------------------------------------------------------
# Against the shipped corpus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus_engine():
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    return g, GraphEngine(g, cfg)


def test_named_risk_rag_states(corpus_engine):
    _, eng = corpus_engine
    states = {r.named_risk.id: r.state for r in eng.all_named_risk_residuals()}
    # Single-acceptance breach (region concentration) and accumulation breach.
    assert states["NR-PLATFORM-OUTAGE"] == RAG_OVER
    assert states["NR-PROD-COMPROMISE"] == RAG_OVER
    # A well-within risk reads amber (unused tolerance), never a green all-clear.
    assert states["NR-VENDOR-ACCESS"] == RAG_BELOW


def test_named_risk_drivers_are_factor_moving_only(corpus_engine):
    _, eng = corpus_engine
    r = eng.named_risk_residual("NR-PROD-COMPROMISE")
    assert r.drivers  # something drives it
    assert all(c.issue.moves_a_factor for c in r.drivers)  # never a finding


def test_legacy_exception_contributes_to_bridged_scenario(corpus_engine):
    _, eng = corpus_engine
    res = eng.scenario_residual("SCN-2026-0001")
    assert "EXC-2026-0142" in {c.issue.id for c in res.contributors}


def test_portfolio_over_declared_appetite(corpus_engine):
    _, eng = corpus_engine
    p = eng.portfolio()
    assert p.over_appetite is True         # the aggregate exceeds the $10M line
    assert p.capacity_breached is True     # and the $15M hard line
    assert p.band.low > p.appetite


def test_control_health_stories(corpus_engine):
    _, eng = corpus_engine
    by_id = {h.control.id: h for h in eng.all_control_health()}
    # §5.4: a control with poor health from clustered findings.
    assert by_id["A.8.5"].health == "red"
    assert by_id["A.8.5"].findings_by_severity.get("high", 0) >= 2
    # Accepted vulns cluster on the vuln-management control.
    assert by_id["A.8.8"].health == "red"
    assert by_id["A.8.8"].open_gap_count >= 2
    # §5.5: a control clean on findings but amber on stale/missing evidence.
    assert by_id["A.8.32"].clean_but_unproven is True
    assert by_id["A.8.32"].health == "amber"
    assert by_id["A.8.32"].evidence_status == "missing"


def test_control_health_never_touches_residual(corpus_engine):
    # Health is diagnostic only. The red A.8.5 control's findings are not
    # contributors to the scenario they touch.
    _, eng = corpus_engine
    res = eng.scenario_residual("SCN-2026-0001")
    assert all(c.issue.type in ("exception", "vuln") for c in res.contributors)


def test_emerging_items_are_ai_vectored_and_would_breach(corpus_engine):
    _, eng = corpus_engine
    items = eng.emerging_items()
    assert len(items) >= 3
    assert all(i.trajectory == "rising" for i in items)
    assert all("ai" in i.scenario.vectors for i in items)
    assert any(i.would_breach for i in items)


def test_kri_triggers_surface_as_signals(corpus_engine):
    _, eng = corpus_engine
    breached = {k.kri_id for k in eng.breached_kris()}
    assert "KRI-MFA-COVERAGE" in breached
    # The MFA-coverage KRI is a signal on the compromise risk, not its own term.
    sigs = {s.kri_id: s.status for s in eng.kri_signals_for_named_risk("NR-PROD-COMPROMISE")}
    assert sigs.get("KRI-MFA-COVERAGE") == "breached"
