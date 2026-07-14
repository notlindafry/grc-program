"""The v2 GRC-ecosystem graph: loading, cardinalities, and the new invariants.

Two layers of test:

* Against the shipped ``data/`` corpus, that the graph loads cleanly, every
  SPEC §3 cardinality resolves, and the derived adjacency wiring is correct.
* Against hand-built minimal graphs, that each new validation invariant fires
  (issue -> scenario, issue type, horizon completeness, control mapping, finding
  severity, tree links) and only when it should.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_ledger.config import Config
from risk_ledger.graph import Graph, assemble_graph
from risk_ledger.loader import load_graph
from risk_ledger.models import (
    Control,
    Domain,
    Enterprise,
    Estimator,
    HorizonItem,
    IssueRecord,
    KRI,
    NamedRisk,
    Scenario,
)
from risk_ledger.validation import validate_graph

DATA = Path(__file__).resolve().parent.parent / "data"
AS_OF = dt.date(2026, 6, 18)


# ---------------------------------------------------------------------------
# Against the shipped corpus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def graph() -> Graph:
    return load_graph(DATA)


@pytest.fixture(scope="module")
def problems(graph):
    return validate_graph(graph, Config(as_of=AS_OF))


def test_corpus_graph_loads_without_errors(graph, problems):
    assert graph.load_errors == []
    hard = [p for p in problems if p.severity == "error"]
    assert hard == [], [p.message for p in hard]


def test_entity_counts(graph):
    assert len(graph.domains) == 7  # the seven Tier-1 domains
    assert 15 <= len(graph.named_risks) <= 25  # SPEC §5 volumes
    assert len(graph.controls) == 93  # full ISO 27001:2022 Annex A set
    # Theme split 37/8/14/34.
    themes = {}
    for c in graph.controls.values():
        themes[c.theme] = themes.get(c.theme, 0) + 1
    assert themes == {"Organizational": 37, "People": 8, "Physical": 14, "Technological": 34}


def test_issue_types_present(graph):
    assert len(graph.issues_for("exception")) == 49  # the migrated legacy exceptions
    assert len(graph.issues_for("vuln")) >= 1
    assert len(graph.issues_for("finding")) >= 1


def test_every_cardinality_resolves(graph):
    summary = graph.cardinality_summary()
    flags = summary["flags"]
    assert flags["orphan_scenarios"] == 0
    assert flags["issues_without_scenario"] == 0
    # Every named risk resolves to a domain, every scenario to a named risk,
    # every control to a governing policy.
    assert all(nr.domain in graph.domains for nr in graph.named_risks.values())
    assert all(s.named_risk in graph.named_risks for s in graph.scenarios.values())
    assert all(c.policy in graph.policies for c in graph.controls.values())


def test_legacy_exception_bridges_to_scenario(graph):
    # A migrated exception still names a mapped_risk; the graph resolves it to the
    # scenario that adopted that id via legacy_risk.
    exc = next(i for i in graph.issues if i.id == "EXC-2026-0142")
    assert exc.type == "exception"
    resolved = graph.resolved_scenarios(exc)
    assert resolved == ["SCN-2026-0001"]  # RISK-ACCT-TAKEOVER -> its scenario
    assert exc.id in graph.issues_of_scenario["SCN-2026-0001"]


def test_derived_adjacency(graph):
    # Domain -> named risks down-tree.
    assert "NR-PROD-COMPROMISE" in graph.named_risks_of_domain["TR-SECURITY"]
    # Named risk -> scenarios.
    assert "SCN-2026-0001" in graph.scenarios_of_named_risk["NR-PROD-COMPROMISE"]
    # Control -> policy grouping.
    assert graph.controls_of_policy["POL-ACCESS-CONTROL"]
    # Evidence -> control.
    assert graph.evidence_of_control["A.8.5"]
    # KRI -> scenario (informs).
    assert "KRI-MFA-COVERAGE" in graph.kris_of_scenario["SCN-2026-0001"]
    # Named risk -> OKR (threatens).
    assert "NR-PROD-COMPROMISE" in graph.named_risks_of_okr["gcloud-migration"]
    # Remediation -> scenario / issue (m2m).
    assert "REM-2026-0001" in graph.remediations_of_scenario["SCN-2026-0001"]
    assert "REM-2026-0001" in graph.remediations_of_issue["VULN-2026-0001"]


def test_emerging_scenarios_carry_wide_ai_bands(graph):
    emerging = [s for s in graph.scenarios.values() if s.is_emerging]
    assert len(emerging) >= 2
    assert all(s.trajectory == "rising" for s in emerging)
    assert any("ai" in s.vectors for s in emerging)


def test_derived_evidence_status(graph):
    # Fresh, stale, and missing all present (the provability signal, SPEC §5.5).
    statuses = {e.status(AS_OF) for e in graph.evidence.values()}
    assert {"fresh", "stale", "missing"} <= statuses


def test_derived_kri_status(graph):
    statuses = {k.status for k in graph.kris.values()}
    assert "breached" in statuses  # KRI breaches feed the horizon view (SPEC §5.10)


def test_only_expected_flags(problems):
    # 3 legacy trust flags (1 uncalibrated + 2 stale) and 3 deliberate orphan
    # controls; nothing else should flag on the shipped corpus.
    codes = sorted(p.code for p in problems if p.severity == "flag")
    assert codes == [
        "control_maps_no_risk",
        "control_maps_no_risk",
        "control_maps_no_risk",
        "estimator_stale",
        "estimator_stale",
        "estimator_uncalibrated",
    ]


# ---------------------------------------------------------------------------
# The new invariants, on minimal hand-built graphs
# ---------------------------------------------------------------------------


def _minimal_graph(**over) -> Graph:
    """A tiny valid graph; override any register to exercise one invariant."""
    g = Graph()
    g.enterprise = over.get("enterprise", Enterprise.parse(
        {"revenue_annual": 2e9, "capacity_materiality": 15e6, "appetite_pct_of_revenue": 0.005}
    ))
    g.domains = over.get("domains", {"TR-SECURITY": Domain.parse("TR-SECURITY", {"title": "Security"})})
    g.named_risks = over.get("named_risks", {
        "NR-X": NamedRisk.parse("NR-X", {"domain": "TR-SECURITY", "appetite_threshold": 1e6})
    })
    g.scenarios = over.get("scenarios", {
        "SCN-1": Scenario.parse({
            "id": "SCN-1", "named_risk": "NR-X",
            "baseline": {
                "opportunity_frequency_90ci": [10, 40],
                "probability_of_realization_90ci": [0.005, 0.02],
                "loss_magnitude_90ci": [200000, 500000],
            },
        }, "SCN-1.yaml")
    })
    g.controls = over.get("controls", {})
    g.policies = over.get("policies", {"POL-X": None} if False else {})
    g.kris = over.get("kris", {})
    g.horizon = over.get("horizon", {})
    g.issues = over.get("issues", [])
    g.estimators = over.get("estimators", {
        "r.chen@company.com": Estimator.parse("r.chen@company.com",
                                              {"calibrated": True, "calibrated_on": "2026-03-15"})
    })
    return assemble_graph(g)


def _codes(problems, severity=None):
    return {p.code for p in problems if severity is None or p.severity == severity}


def test_issue_must_map_to_a_scenario():
    issue = IssueRecord.parse(
        {"id": "VULN-1", "type": "vuln", "moves": "probability_of_realization",
         "with_acceptance_90ci": [0.01, 0.05], "estimated_by": "r.chen@company.com"},
        "VULN-1.yaml",
    )
    g = _minimal_graph(issues=[issue])
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "issue_no_scenario" in _codes(problems, "error")


def test_issue_type_must_be_valid():
    issue = IssueRecord.parse(
        {"id": "ISS-1", "type": "nonsense", "mapped_scenarios": ["SCN-1"]}, "ISS-1.yaml")
    g = _minimal_graph(issues=[issue])
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "issue_type_invalid" in _codes(problems, "error")


def test_finding_needs_a_bounded_severity():
    issue = IssueRecord.parse(
        {"id": "FND-1", "type": "finding", "severity": "catastrophic",
         "mapped_scenarios": ["SCN-1"]}, "FND-1.yaml")
    g = _minimal_graph(issues=[issue])
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "finding_severity_invalid" in _codes(problems, "error")


def test_finding_is_not_factor_moving():
    issue = IssueRecord.parse(
        {"id": "FND-2", "type": "finding", "severity": "high",
         "mapped_scenarios": ["SCN-1"]}, "FND-2.yaml")
    assert not issue.moves_a_factor
    assert not issue.counts_in_bands  # the one-path-into-residual rule (SPEC §4)


def test_horizon_needs_both_domain_and_kri():
    incomplete = HorizonItem.parse("HZN-1", {"title": "x", "candidate_domain": "TR-SECURITY"})
    g = _minimal_graph(horizon={"HZN-1": incomplete})
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "horizon_incomplete" in _codes(problems, "error")


def test_unmapped_control_is_flagged_not_rejected():
    ctrl = Control.parse("A.5.6", {"title": "x", "theme": "Organizational", "policy": ""})
    g = _minimal_graph(controls={"A.5.6": ctrl})
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "control_maps_no_risk" in _codes(problems, "flag")
    assert "control_maps_no_risk" not in _codes(problems, "error")  # a flag, never a hard error


def test_scenario_needs_a_known_named_risk():
    orphan = Scenario.parse({
        "id": "SCN-2", "named_risk": "NR-GHOST",
        "baseline": {
            "opportunity_frequency_90ci": [10, 40],
            "probability_of_realization_90ci": [0.005, 0.02],
            "loss_magnitude_90ci": [200000, 500000],
        },
    }, "SCN-2.yaml")
    g = _minimal_graph(scenarios={"SCN-2": orphan})
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "scenario_named_risk_unknown" in _codes(problems, "error")


def test_named_risk_needs_a_known_domain():
    nr = {"NR-Y": NamedRisk.parse("NR-Y", {"domain": "TR-GHOST", "appetite_threshold": 1e6})}
    g = _minimal_graph(named_risks=nr, scenarios={})
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "named_risk_domain_unknown" in _codes(problems, "error")


def test_appetite_above_capacity_flags():
    ent = Enterprise.parse(
        {"revenue_annual": 2e9, "capacity_materiality": 5e6, "appetite_pct_of_revenue": 0.005})
    assert ent.declared_appetite == 10e6  # exceeds the 5M capacity
    g = _minimal_graph(enterprise=ent)
    problems = validate_graph(g, Config(as_of=AS_OF))
    assert "appetite_above_capacity" in _codes(problems, "flag")
