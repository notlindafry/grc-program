"""Load a corpus of YAML records from a data directory.

Layout::

    data/
      risks.yaml          # the light register: baseline + appetite per risk
      estimators.yaml     # the calibration gate
      okrs.yaml           # objective + key results (+ optional period_end) per OKR
      exceptions/
        EXC-*.yaml        # one file per exception
      config.yaml         # optional run configuration

Parsing is defensive. A file that cannot be read as a YAML mapping is recorded
as a load error and skipped rather than crashing the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .graph import Graph, assemble_graph
from .models import (
    OKR,
    Control,
    Domain,
    Enterprise,
    Estimator,
    Evidence,
    Exception_,
    HorizonItem,
    IssueRecord,
    KRI,
    NamedRisk,
    Policy,
    Remediation,
    Risk,
    Scenario,
)


@dataclass
class Corpus:
    risks: dict[str, Risk] = field(default_factory=dict)
    estimators: dict[str, Estimator] = field(default_factory=dict)
    okrs: dict[str, OKR] = field(default_factory=dict)
    exceptions: list[Exception_] = field(default_factory=list)
    remediations: list[Remediation] = field(default_factory=list)
    load_errors: list[str] = field(default_factory=list)

    def active_exceptions(self) -> list[Exception_]:
        return [e for e in self.exceptions if e.is_active]


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def load_corpus(data_dir: Path) -> Corpus:
    data_dir = Path(data_dir)
    corpus = Corpus()

    risks_path = data_dir / "risks.yaml"
    if risks_path.exists():
        raw = _load_yaml(risks_path) or {}
        if isinstance(raw, dict):
            for rid, spec in raw.items():
                corpus.risks[str(rid)] = Risk.parse(str(rid), spec or {})
        else:
            corpus.load_errors.append(f"{risks_path}: expected a mapping of risk-id -> spec")
    else:
        corpus.load_errors.append(f"{risks_path}: missing (no risk register)")

    est_path = data_dir / "estimators.yaml"
    if est_path.exists():
        raw = _load_yaml(est_path) or {}
        if isinstance(raw, dict):
            for email, spec in raw.items():
                corpus.estimators[str(email)] = Estimator.parse(str(email), spec or {})
        else:
            corpus.load_errors.append(f"{est_path}: expected a mapping of email -> spec")

    okr_path = data_dir / "okrs.yaml"
    if okr_path.exists():
        raw = _load_yaml(okr_path) or {}
        if isinstance(raw, dict):
            for oid, spec in raw.items():
                corpus.okrs[str(oid)] = OKR.parse(str(oid), spec or {})
        else:
            corpus.load_errors.append(f"{okr_path}: expected a mapping of okr-id -> spec")

    exc_dir = data_dir / "exceptions"
    if exc_dir.exists():
        for path in sorted(exc_dir.glob("*.yaml")):
            try:
                raw = _load_yaml(path)
            except yaml.YAMLError as exc:  # malformed YAML
                corpus.load_errors.append(f"{path}: invalid YAML ({exc})")
                continue
            if not isinstance(raw, dict):
                corpus.load_errors.append(f"{path}: expected a mapping at the top level")
                continue
            corpus.exceptions.append(Exception_.parse(raw, str(path)))
    else:
        corpus.load_errors.append(f"{exc_dir}: missing (no exceptions directory)")

    rem_dir = data_dir / "remediations"
    if rem_dir.exists():
        for path in sorted(rem_dir.glob("*.yaml")):
            try:
                raw = _load_yaml(path)
            except yaml.YAMLError as exc:  # malformed YAML
                corpus.load_errors.append(f"{path}: invalid YAML ({exc})")
                continue
            if not isinstance(raw, dict):
                corpus.load_errors.append(f"{path}: expected a mapping at the top level")
                continue
            corpus.remediations.append(Remediation.parse(raw, str(path)))

    return corpus


# ===========================================================================
# v2 GRC-ecosystem graph loader (SPEC §2, §3)
# ---------------------------------------------------------------------------
# Loads the new entity registers and per-record directories and assembles the
# derived relational graph. Kept separate from ``load_corpus`` so the legacy
# engine/report path is untouched during the Day-1 schema build. Both read the
# same ``data/`` directory; the graph additionally reads exceptions from the
# existing ``exceptions/`` folder (as ``type: exception`` issues) so the migrated
# corpus links up without duplicating those files.
# ===========================================================================


def _load_register(path: Path, parse, errors: list[str], label: str) -> dict:
    """Load a single-file mapping-of-id->spec register, defensively."""
    out: dict = {}
    if not path.exists():
        return out
    try:
        raw = _load_yaml(path) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML ({exc})")
        return out
    if not isinstance(raw, dict):
        errors.append(f"{path}: expected a mapping of {label}-id -> spec")
        return out
    for key, spec in raw.items():
        out[str(key)] = parse(str(key), spec or {})
    return out


def _load_record_dir(directory: Path, parse, errors: list[str]) -> list:
    """Load a directory of one-record-per-file YAML documents, defensively."""
    out: list = []
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = _load_yaml(path)
        except yaml.YAMLError as exc:
            errors.append(f"{path}: invalid YAML ({exc})")
            continue
        if not isinstance(raw, dict):
            errors.append(f"{path}: expected a mapping at the top level")
            continue
        out.append(parse(raw, str(path)))
    return out


def load_graph(data_dir: Path) -> Graph:
    """Load the v2 corpus and assemble the derived relational graph (SPEC §3)."""
    data_dir = Path(data_dir)
    graph = Graph()
    errors = graph.load_errors

    ent_path = data_dir / "enterprise.yaml"
    if ent_path.exists():
        raw = _load_yaml(ent_path) or {}
        if isinstance(raw, dict):
            graph.enterprise = Enterprise.parse(raw)
        else:
            errors.append(f"{ent_path}: expected a mapping")

    graph.domains = _load_register(data_dir / "domains.yaml", Domain.parse, errors, "domain")
    graph.named_risks = _load_register(
        data_dir / "named_risks.yaml", NamedRisk.parse, errors, "named-risk"
    )
    graph.controls = _load_register(data_dir / "controls.yaml", Control.parse, errors, "control")
    graph.policies = _load_register(data_dir / "policies.yaml", Policy.parse, errors, "policy")
    graph.evidence = _load_register(data_dir / "evidence.yaml", Evidence.parse, errors, "evidence")
    graph.kris = _load_register(data_dir / "kris.yaml", KRI.parse, errors, "kri")
    graph.horizon = _load_register(data_dir / "horizon.yaml", HorizonItem.parse, errors, "horizon")
    graph.okrs = _load_register(data_dir / "okrs.yaml", OKR.parse, errors, "okr")
    graph.estimators = _load_register(data_dir / "estimators.yaml", Estimator.parse, errors, "estimator")

    scenarios = _load_record_dir(data_dir / "scenarios", Scenario.parse, errors)
    graph.scenarios = {s.id: s for s in scenarios if s.id}

    # Issues: the v2 corpus is self-contained under issues/ (exceptions, vulns,
    # findings), independently calibrated. The legacy exceptions/ directory feeds
    # the v1 engine only and is not read here, so the two corpora stay decoupled
    # and the v2 effects can be rescaled without disturbing the frozen v1 tests.
    graph.issues = _load_record_dir(data_dir / "issues", IssueRecord.parse, errors)

    # v2 remediations live in graph_remediations/ (native-queue work with m2m
    # links to scenarios/issues), kept apart from the legacy remediations/ set.
    graph.remediations = _load_record_dir(data_dir / "graph_remediations", Remediation.parse, errors)

    return assemble_graph(graph)
