"""The derived relational graph (SPEC §0, §1, §3).

YAML stays the system of record. The relational structure is *derived at build
time* — assembled here into an in-memory graph, never persisted back. The model
spine is::

    Domain (Tier 1)  <-  NamedRisk (Tier 2)  <-  Scenario (Tier 3)  <-  Issue

with Controls mitigating NamedRisks and tracing up to Policies, Evidence proving
Controls, KRIs informing Scenario factors, Remediations addressing Scenarios and
Issues, and NamedRisks threatening OKRs. Every edge in SPEC §3's cardinality
table is materialised as an adjacency map below and can be summarised for the
Day-1 "confirm the cardinalities" gate via :meth:`Graph.cardinality_summary`.

This module only *wires* records together and resolves the legacy bridge (a
migrated exception still names a ``mapped_risk``; a scenario carrying that id in
``legacy_risk`` adopts it). It computes no quantities — the engine (Day 2) does.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .models import (
    Control,
    Domain,
    Enterprise,
    Estimator,
    Evidence,
    HorizonItem,
    IssueRecord,
    KRI,
    NamedRisk,
    OKR,
    Policy,
    Remediation,
    Scenario,
)


@dataclass
class Graph:
    """The assembled, in-memory relational view over the YAML corpus.

    Registers are dicts keyed by id; per-record collections are lists. The
    ``*_of`` / ``*_for`` adjacency maps are derived once at construction and are
    the read model every downstream view consumes.
    """

    enterprise: Optional[Enterprise] = None
    domains: dict[str, Domain] = field(default_factory=dict)
    named_risks: dict[str, NamedRisk] = field(default_factory=dict)
    scenarios: dict[str, Scenario] = field(default_factory=dict)
    issues: list[IssueRecord] = field(default_factory=list)
    controls: dict[str, Control] = field(default_factory=dict)
    policies: dict[str, Policy] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    kris: dict[str, KRI] = field(default_factory=dict)
    horizon: dict[str, HorizonItem] = field(default_factory=dict)
    remediations: list[Remediation] = field(default_factory=list)
    okrs: dict[str, OKR] = field(default_factory=dict)
    estimators: dict[str, Estimator] = field(default_factory=dict)

    load_errors: list[str] = field(default_factory=list)

    # -- derived adjacency (built in _assemble) -----------------------------
    # Down-tree (parent -> children):
    named_risks_of_domain: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    scenarios_of_named_risk: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    issues_of_scenario: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    # Cross-links:
    controls_of_named_risk: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    controls_of_policy: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    evidence_of_control: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    kris_of_scenario: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    remediations_of_scenario: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    remediations_of_issue: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    named_risks_of_okr: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # Legacy bridge: legacy risk-id -> scenario id(s) that adopted it.
    _scenario_of_legacy_risk: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def resolved_scenarios(self, issue: IssueRecord) -> list[str]:
        """The scenario ids an issue maps to, resolving the legacy bridge.

        A v2 issue names ``mapped_scenarios`` directly. A migrated legacy
        exception names a single ``mapped_risk``; if a scenario adopted that id
        via ``legacy_risk`` we resolve to it, so the existing corpus links up
        without editing every exception file.
        """
        if issue.mapped_scenarios:
            return issue.mapped_scenarios
        if issue.mapped_risk and issue.mapped_risk in self._scenario_of_legacy_risk:
            return [self._scenario_of_legacy_risk[issue.mapped_risk]]
        return []

    def issues_for(self, itype: Optional[str] = None) -> list[IssueRecord]:
        if itype is None:
            return list(self.issues)
        return [i for i in self.issues if i.type == itype]

    # ------------------------------------------------------------------
    def _assemble(self) -> None:
        """Materialise every SPEC §3 edge as an adjacency map."""
        self._scenario_of_legacy_risk = {
            s.legacy_risk: sid for sid, s in self.scenarios.items() if s.legacy_risk
        }

        for did in self.domains:
            self.named_risks_of_domain.setdefault(did, [])
        for nid, nr in self.named_risks.items():
            if nr.domain:
                self.named_risks_of_domain[nr.domain].append(nid)
            self.scenarios_of_named_risk.setdefault(nid, [])
            for okr_id in nr.threatens_okrs:
                self.named_risks_of_okr[okr_id].append(nid)

        for sid, sc in self.scenarios.items():
            if sc.named_risk:
                self.scenarios_of_named_risk[sc.named_risk].append(sid)
            self.issues_of_scenario.setdefault(sid, [])
            self.kris_of_scenario.setdefault(sid, [])

        for issue in self.issues:
            for sid in self.resolved_scenarios(issue):
                self.issues_of_scenario[sid].append(issue.id)

        for cid, ctrl in self.controls.items():
            for nid in ctrl.mapped_named_risks:
                self.controls_of_named_risk[nid].append(cid)
            if ctrl.policy:
                self.controls_of_policy[ctrl.policy].append(cid)
            self.evidence_of_control.setdefault(cid, [])

        for eid, ev in self.evidence.items():
            for cid in ev.supports_controls:
                self.evidence_of_control[cid].append(eid)

        for kid, kri in self.kris.items():
            for target in kri.informs:  # a KRI may inform a scenario or a named risk
                if target in self.scenarios:
                    self.kris_of_scenario[target].append(kid)

        for rem in self.remediations:
            for sid in rem.addresses_scenarios:
                self.remediations_of_scenario[sid].append(rem.id)
            for iid in rem.addresses_issues:
                self.remediations_of_issue[iid].append(rem.id)

    # ------------------------------------------------------------------
    def cardinality_summary(self) -> dict[str, object]:
        """A compact confirmation of SPEC §3, for the Day-1 gate and tests.

        Reports the count of each entity and, for each relationship, how many
        parent records have at least one child (so an orphan is visible as a
        gap between the entity count and its participating count).
        """
        n_orphan_scn = sum(
            1 for s in self.scenarios.values() if not s.named_risk or s.named_risk not in self.named_risks
        )
        n_unmapped_ctrl = sum(1 for c in self.controls.values() if not c.mapped_named_risks)
        n_issue_no_scn = sum(1 for i in self.issues if not self.resolved_scenarios(i))
        return {
            "entities": {
                "domains": len(self.domains),
                "named_risks": len(self.named_risks),
                "scenarios": len(self.scenarios),
                "issues": len(self.issues),
                "issues_by_type": {
                    t: len(self.issues_for(t)) for t in ("exception", "vuln", "finding")
                },
                "controls": len(self.controls),
                "policies": len(self.policies),
                "evidence": len(self.evidence),
                "kris": len(self.kris),
                "horizon": len(self.horizon),
                "remediations": len(self.remediations),
                "okrs": len(self.okrs),
            },
            "edges": {
                "named_risk->domain (tree)": self._tree_ok(
                    self.named_risks, lambda nr: nr.domain, self.domains
                ),
                "scenario->named_risk (tree)": self._tree_ok(
                    self.scenarios, lambda s: s.named_risk, self.named_risks
                ),
                "control->policy (tree)": self._tree_ok(
                    self.controls, lambda c: c.policy, self.policies
                ),
                "issue->scenario (m2m)": f"{len(self.issues) - n_issue_no_scn}/{len(self.issues)} issues mapped",
                "control->named_risk (m2m)": f"{len(self.controls) - n_unmapped_ctrl}/{len(self.controls)} controls mapped",
            },
            "flags": {
                "orphan_scenarios": n_orphan_scn,
                "unmapped_controls": n_unmapped_ctrl,
                "issues_without_scenario": n_issue_no_scn,
            },
        }

    @staticmethod
    def _tree_ok(children: dict, parent_of, parents: dict) -> str:
        resolved = sum(1 for c in children.values() if parent_of(c) in parents)
        return f"{resolved}/{len(children)} resolve to a parent"


def assemble_graph(graph: Graph) -> Graph:
    """Wire a freshly loaded :class:`Graph` and return it (in place)."""
    graph._assemble()
    return graph
