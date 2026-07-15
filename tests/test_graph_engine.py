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
    # The aggregate-over-appetite signal (SPEC §4) is mean-based; capacity is read
    # as a tail probability, not a mean test (SPEC v2.2 §E2).
    assert p.over_appetite is True
    assert p.band.mean > p.capacity
    assert 0.0 <= p.p_over_capacity <= 1.0 and p.p_over_capacity > 0.5


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


def test_issue_contributes_to_its_scenario(corpus_engine):
    _, eng = corpus_engine
    res = eng.scenario_residual("SCN-2026-0001")
    assert "EXC-2026-0101" in {c.issue.id for c in res.contributors}


def test_portfolio_over_appetite_under_capacity(corpus_engine):
    # The aggregate is OVER the $10M appetite (the signal fires) with its mean
    # UNDER the $15M capacity line -- a governance moment, not a catastrophe. The
    # capacity read is a tail probability, reported honestly (SPEC v2.2 §E).
    _, eng = corpus_engine
    p = eng.portfolio()
    assert p.over_appetite is True
    assert p.appetite < p.band.mean < p.capacity
    assert 0.0 < p.p_over_capacity < 0.5       # a real tail, not a coin-flip
    assert p.p_over_appetite > 0.9             # decisively over the appetite line
    assert p.band.mean < 0.01 * 2_000_000_000  # well under 1% of revenue (SPEC §I.10)


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


# --- Day-3 designed stories (SPEC v2.2 §B, §E, §F) -------------------------


def test_rag_spread_is_a_reasonable_outcome(corpus_engine):
    # The spread is a JUDGED outcome of authored appetite meeting tuned exposure,
    # NOT a fitted target (SPEC v2.2 §B): a few over, green demonstrably
    # achievable, a majority below, and no colour the default.
    _, eng = corpus_engine
    from collections import Counter
    spread = Counter(r.state for r in eng.all_named_risk_residuals())
    total = sum(spread.values())
    assert spread[RAG_OVER] >= 2                      # a few breaches
    assert spread[RAG_AT] >= 2                        # green is demonstrably achievable
    assert spread[RAG_BELOW] > total / 2              # over-controlling is the majority (on-thesis)
    assert spread[RAG_BELOW] < total                  # ...but not the only colour


def test_exactly_one_amber_end_to_end_domain(corpus_engine):
    # SPEC v2.2 §F: exactly one domain reads amber end to end, and it is Privacy
    # -- regulated, engineering-adjacent, and the one a VP files as "legal's".
    _, eng = corpus_engine
    amber = [d.domain.id for d in eng.all_domain_rollups() if d.amber_end_to_end]
    assert amber == ["TR-PRIVACY"]
    privacy = eng.domain_rollup("TR-PRIVACY")
    assert len(privacy.named_risk_ids) >= 4           # "end to end" across a real domain


def test_exceedance_probabilities(corpus_engine):
    # SPEC v2.2 §E: the capacity read is the tail probability, not a mean test.
    _, eng = corpus_engine
    p = eng.portfolio()
    assert 0.0 < p.p_over_appetite <= 1.0
    assert 0.0 < p.p_over_capacity < 0.5
    # An over-appetite named risk exceeds its own threshold on most trials.
    over = next(r for r in eng.all_named_risk_residuals() if r.state == RAG_OVER)
    assert over.p_over_threshold > 0.5


def test_appetite_is_authored_not_derived(corpus_engine):
    # SPEC v2.2 §D: every named risk carries a round-number authored threshold and
    # a rationale; no threshold is a fitted function of its residual.
    graph, _ = corpus_engine
    for nr in graph.named_risks.values():
        assert nr.appetite_threshold and nr.appetite_threshold % 50_000 == 0  # round number
        assert nr.appetite_rationale                                          # authored reason
        assert nr.appetite_threshold <= graph.enterprise.capacity_materiality  # §D1


def test_privacy_has_a_dramatic_standout(corpus_engine):
    # At least one Privacy risk sits dramatically under its authored threshold
    # (residual mean ~10-20% of appetite) -- unused tolerance, over-controlled.
    _, eng = corpus_engine
    ratios = [
        r.band.mean / r.threshold
        for r in eng.all_named_risk_residuals()
        if eng.graph.named_risks[r.named_risk.id].domain == "TR-PRIVACY"
    ]
    assert all(x < 0.75 for x in ratios)              # every Privacy risk is BELOW
    assert min(ratios) < 0.2                          # one dramatically so


def test_orphans_have_no_funded_remediation(corpus_engine):
    # SPEC §E story 3: >=2 orphan risks (OVER, no funded remediation addressing them).
    graph, eng = corpus_engine
    funded = {"funded", "in_progress"}
    orphans = []
    for r in eng.all_named_risk_residuals():
        if r.state != RAG_OVER:
            continue
        scn_ids = set(r.scenario_ids)
        rem_ids = {rid for sid in scn_ids for rid in graph.remediations_of_scenario.get(sid, [])}
        rems = [rm for rm in graph.remediations if rm.id in rem_ids]
        if not any(rm.status in funded for rm in rems):
            orphans.append(r.named_risk.id)
    assert {"NR-PLATFORM-OUTAGE", "NR-PCI-SCOPE"} <= set(orphans)


def test_no_scenario_multiplier_over_5x(corpus_engine):
    # SPEC v2.1 §F7: no managed scenario's residual/baseline multiplier exceeds ~5x.
    _, eng = corpus_engine
    for sid, res in ((s, eng.scenario_residual(s)) for s in eng.graph.scenarios):
        if res is None or eng.graph.scenarios[sid].is_emerging or res.baseline.high <= 0:
            continue
        assert res.band.high / res.baseline.high <= 5.0, sid


def test_no_managed_scenario_over_capacity(corpus_engine):
    # SPEC v2.1 §F4/B2: no managed scenario residual crosses the $15M capacity line.
    _, eng = corpus_engine
    assert eng.scenarios_over_capacity() == []


def test_diverted_to_starvation_chain_exists(corpus_engine):
    # SPEC §E story 7: exceptions reallocated to a named launch OKR.
    graph, _ = corpus_engine
    diverted = [i for i in graph.issues
                if i.type == "exception" and i.reason == "resource_reallocation" and i.diverted_to]
    assert len(diverted) >= 3
    assert all(i.diverted_to in graph.okrs for i in diverted)


def test_incident_mapping_stored_as_data(corpus_engine):
    # SPEC §8 / §E story 8: the offline AI incident->scenario mapping, as data.
    graph, _ = corpus_engine
    scn = graph.scenarios["SCN-2026-0019"]
    assert scn.incident is not None
    assert scn.incident["suggested_named_risk"] == "NR-PROD-COMPROMISE"
    assert scn.incident["mapped_by"] == "offline-ai-incident-mapper"
