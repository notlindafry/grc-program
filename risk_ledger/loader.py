"""Load a corpus of YAML records from a data directory.

Layout::

    data/
      risks.yaml          # the light register: baseline + appetite per risk
      estimators.yaml     # the calibration gate
      initiatives.yaml    # stated objective (+ optional cutover) per initiative
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

from .models import Estimator, Exception_, Initiative, Risk


@dataclass
class Corpus:
    risks: dict[str, Risk] = field(default_factory=dict)
    estimators: dict[str, Estimator] = field(default_factory=dict)
    initiatives: dict[str, Initiative] = field(default_factory=dict)
    exceptions: list[Exception_] = field(default_factory=list)
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

    init_path = data_dir / "initiatives.yaml"
    if init_path.exists():
        raw = _load_yaml(init_path) or {}
        if isinstance(raw, dict):
            for iid, spec in raw.items():
                corpus.initiatives[str(iid)] = Initiative.parse(str(iid), spec or {})
        else:
            corpus.load_errors.append(f"{init_path}: expected a mapping of initiative-id -> spec")

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

    return corpus
