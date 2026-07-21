"""Load the GRC-ecosystem corpus from a data directory and assemble the graph.

The YAML under ``data/`` is the system of record; the relational structure is
derived at build time (:mod:`risk_ledger.graph`). Parsing is defensive: a file
that cannot be read as a YAML mapping is recorded as a load error and skipped
rather than crashing the run.
"""

from __future__ import annotations

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
    HorizonItem,
    IssueRecord,
    KRI,
    NamedRisk,
    Policy,
    Remediation,
    Scenario,
)


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


# ===========================================================================
# GRC-ecosystem graph loader (SPEC §2, §3)
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

    # Issues: the v2 corpus is self-contained under issues/ (exceptions and
    # findings), independently calibrated. The legacy exceptions/ directory feeds
    # the v1 engine only and is not read here, so the two corpora stay decoupled
    # and the v2 effects can be rescaled without disturbing the frozen v1 tests.
    graph.issues = _load_record_dir(data_dir / "issues", IssueRecord.parse, errors)

    # Remediations: native-queue work with m2m links to scenarios/issues.
    graph.remediations = _load_record_dir(data_dir / "remediations", Remediation.parse, errors)

    return assemble_graph(graph)
