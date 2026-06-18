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
    assert len(corpus.exceptions) == 49
    assert [e for e in corpus.exceptions if e.rejected] == []
    flagged = [e for e in corpus.exceptions if e.flags]
    assert len(flagged) == 8  # 4 non-plan + 1 realloc-no-dest + 3 trust


def test_calibration_confidence_story(built):
    corpus, _, _ = built
    untrusted = [e for e in corpus.exceptions if e.trust_flags]
    assert len(untrusted) == 3  # -> "46 of 49 calibrated"


def test_three_risks_breach(built):
    _, _, engine = built
    states = {r.risk.id: r.state for r in engine.all_residuals()}
    assert states["RISK-ACCT-TAKEOVER"] == "over"
    assert states["RISK-PLATFORM-OUTAGE"] == "over"
    assert states["RISK-DATA-EXFIL"] == "straddling"
    breaching = {"RISK-ACCT-TAKEOVER", "RISK-PLATFORM-OUTAGE", "RISK-DATA-EXFIL"}
    others = [s for rid, s in states.items() if rid not in breaching]
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


def test_platform_outage_is_single_acceptance(built):
    # The Tech Risk example: region concentration dominates (availability parallel
    # to the DLP single-acceptance breach).
    _, _, engine = built
    res = engine.residual("RISK-PLATFORM-OUTAGE")
    top = res.contributors[0]
    assert top.exception.id == "EXC-2026-0170"
    total = sum(c.band.mean for c in res.contributors)
    assert top.band.mean / total > 0.5


def test_ranked_fix_first_order(built):
    corpus, _, engine = built
    fix = fix_first_clusters(engine, corpus)
    controls = [c.control for c in fix]
    # The two biggest single contributors are the platform-outage exceptions;
    # the legacy-auth accumulation and the DLP cluster follow.
    assert controls[:4] == [
        "REL-MULTIREGION-014",
        "REL-DR-TEST-015",
        "IAM-LEGACY-AUTH-001",
        "DLP-EXPORT-001",
    ]
    legacy = next(c for c in fix if c.control == "IAM-LEGACY-AUTH-001")
    assert len(legacy.action_flagged) == 4  # 4 non-plan members carried as malformed


def test_migration_external_footprint(built):
    corpus, _, engine = built
    fp = build_footprint(engine, corpus, "gcloud-migration")
    assert len(fp.internal) == 16
    assert len(fp.external) == 19
    counts = {proj: cnt for proj, (cnt, _) in fp.external_by_project.items()}
    assert counts == {
        "payments-launch": 9,
        "data-platform": 6,
        "trust-and-safety": 3,
        "core-platform": 1,  # skipped DR test extends drift into Tech Risk
    }
    # External footprint still outweighs internal -- the migration's invisible cost.
    assert fp.external_band.mean > fp.internal_band.mean


def test_cli_validate_and_report(capsys):
    assert main(["validate"]) == 0
    out = capsys.readouterr().out
    assert "49 exception record(s)" in out
    assert main(["report"]) == 0
    report = capsys.readouterr().out
    assert "Top line" in report and "gcloud-migration" in report


def test_loader_reports_missing_dir(tmp_path):
    corpus = load_corpus(tmp_path)
    assert any("risks.yaml" in e for e in corpus.load_errors)
