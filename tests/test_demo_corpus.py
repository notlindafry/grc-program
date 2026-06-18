"""Integration test: the shipped demo corpus must keep telling its story.

This pins the end-to-end behaviour against the real ``data/`` corpus so a change
to the engine or a drift in the data is caught immediately.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_ledger.cli import main
from risk_ledger.config import Config
from risk_ledger.engine import Engine
from risk_ledger.loader import load_corpus
from risk_ledger.validation import validate_corpus
from risk_ledger.views.drift import build_footprint
from risk_ledger.views.ranked import fix_first_clusters

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def built():
    config = Config.load(DATA)
    config.as_of = dt.date(2026, 6, 18)
    corpus = load_corpus(DATA)
    validate_corpus(corpus, config)
    engine = Engine(corpus, config)
    return corpus, config, engine


def test_corpus_loads_cleanly(built):
    corpus, _, _ = built
    assert len(corpus.exceptions) == 47
    assert [e for e in corpus.exceptions if e.rejected] == []
    flagged = [e for e in corpus.exceptions if e.flags]
    assert len(flagged) == 8  # 4 non-plan + 1 realloc-no-dest + 3 trust


def test_calibration_confidence_story(built):
    corpus, _, _ = built
    untrusted = [e for e in corpus.exceptions if e.trust_flags]
    assert len(untrusted) == 3  # -> "44 of 47 calibrated"


def test_only_two_risks_breach(built):
    _, _, engine = built
    states = {r.risk.id: r.state for r in engine.all_residuals()}
    assert states["RISK-ACCT-TAKEOVER"] == "over"
    assert states["RISK-DATA-EXFIL"] == "straddling"
    others = [s for rid, s in states.items() if rid not in ("RISK-ACCT-TAKEOVER", "RISK-DATA-EXFIL")]
    assert all(s == "within" for s in others)


def test_acct_takeover_is_accumulation(built):
    _, _, engine = built
    res = engine.residual("RISK-ACCT-TAKEOVER")
    # No single active contributor is over appetite on its own.
    assert all(
        engine.single_acceptance_state("RISK-ACCT-TAKEOVER", c.exception.id) != "over"
        for c in res.contributors
    )


def test_data_exfil_is_single_acceptance(built):
    _, _, engine = built
    res = engine.residual("RISK-DATA-EXFIL")
    top = res.contributors[0]
    assert top.exception.id == "EXC-2026-0133"
    total = sum(c.band.mean for c in res.contributors)
    assert top.band.mean / total > 0.5


def test_ranked_fix_first_order(built):
    corpus, _, engine = built
    fix = fix_first_clusters(engine, corpus)
    assert fix[0].control == "IAM-LEGACY-AUTH-001"
    assert fix[1].control == "DLP-EXPORT-001"
    # The legacy-auth cluster carries its 4 non-plan members as malformed.
    assert len(fix[0].action_flagged) == 4


def test_migration_external_footprint(built):
    corpus, _, engine = built
    fp = build_footprint(engine, corpus, "gcloud-migration")
    assert len(fp.internal) == 15
    assert len(fp.external) == 18
    counts = {proj: cnt for proj, (cnt, _) in fp.external_by_project.items()}
    assert counts == {"payments-launch": 9, "data-platform": 6, "trust-and-safety": 3}
    # External footprint outweighs internal -- the migration's invisible cost.
    assert fp.external_band.mean > fp.internal_band.mean


def test_cli_validate_and_report(capsys):
    assert main(["validate"]) == 0
    out = capsys.readouterr().out
    assert "47 exception record(s)" in out
    assert main(["report"]) == 0
    report = capsys.readouterr().out
    assert "Top line" in report and "gcloud-migration" in report


def test_loader_reports_missing_dir(tmp_path):
    corpus = load_corpus(tmp_path)
    assert any("risks.yaml" in e for e in corpus.load_errors)
