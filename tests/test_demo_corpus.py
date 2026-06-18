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
from risk_ledger.views.ranked import unified_ranking
from risk_ledger.views.renewals import flagged_renewals

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


def test_unified_ranking(built):
    corpus, _, engine = built
    items = unified_ranking(engine, corpus)

    # The list mixes both levers: funded remediations and unfunded breaching
    # clusters appear in the same ranking.
    kinds = {it.kind for it in items}
    assert kinds == {"remediation", "cluster"}

    # Ordered by the risk reduction each buys down (mean), descending.
    means = [it.reduction.mean for it in items]
    assert means == sorted(means, reverse=True)

    # Dedup: a cluster whose control a funded restore covers is not also shown as
    # its own row -- the remediation row stands in for it.
    funded_restored = {
        r.restores_control
        for r in engine.funded_remediations()
        if r.type == "restore" and r.restores_control
    }
    cluster_controls = {it.source_id for it in items if it.kind == "cluster"}
    assert funded_restored.isdisjoint(cluster_controls)
    # Concretely: the three funded restores stand in for their clusters; the
    # DR-test restore is only proposed, so that cluster still appears on its own.
    assert "REL-DR-TEST-015" in cluster_controls          # REM-0004 only proposed
    assert "REL-MULTIREGION-014" not in cluster_controls  # REM-0003 funded restore
    assert "IAM-LEGACY-AUTH-001" not in cluster_controls  # REM-0001 funded restore
    assert "DLP-EXPORT-001" not in cluster_controls       # REM-0002 funded restore

    # The largest single lever is the funded multi-region remediation.
    assert items[0].kind == "remediation"
    assert items[0].source_id == "REM-2026-0003"


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


def test_persistence_flagged(built):
    corpus, config, _ = built
    flagged = flagged_renewals(corpus, config)
    assert {e.id for e in flagged} == {
        "EXC-2026-0310",
        "EXC-2026-0312",
        "EXC-2026-0314",
        "EXC-2026-0313",
        "EXC-2026-0122",
    }
    counts = [e.renewal_count for e in flagged]
    assert counts == sorted(counts, reverse=True)  # descending
    assert counts[0] == 5
    # 0315 is renewed 3x but re-examined; 0311 (1) and 0316 (2) are below threshold.
    renewed_once = [e for e in corpus.exceptions if e.is_active and e.renewal_count >= 1]
    assert len(renewed_once) == 8


def test_new_risk_data_residency(built):
    corpus, _, engine = built
    assert sum(1 for rid in corpus.risks if engine.risk_is_computable(rid)) == 14
    # Material exposure but within appetite today, and no exceptions behind it.
    assert engine.residual("RISK-DATA-RESIDENCY").state == "within"
    assert not any(e.mapped_risk == "RISK-DATA-RESIDENCY" for e in corpus.exceptions)


def test_remediations_loaded(built):
    corpus, _, _ = built
    assert len(corpus.remediations) == 5
    assert [r.id for r in corpus.remediations if r.rejected] == []
    funded = {r.id for r in corpus.remediations if r.is_funded}
    assert "REM-2026-0004" not in funded  # proposed DR-test fix, not funded


def test_over_after_funded_plan_is_platform_only(built):
    corpus, _, engine = built
    post = {r.risk.id: r.state for r in engine.all_post_remediation()}
    assert {rid for rid, s in post.items() if s == "over"} == {"RISK-PLATFORM-OUTAGE"}
    assert post["RISK-ACCT-TAKEOVER"] == "within"   # legacy-auth restore clears it
    assert post["RISK-DATA-EXFIL"] == "within"      # DLP restore clears it
    assert post["RISK-DATA-RESIDENCY"] == "within"  # strengthen keeps it under


def test_demo_risk_reductions(built):
    corpus, _, engine = built
    by_id = {r.id: r for r in corpus.remediations}
    restore = engine.risk_reduction(by_id["REM-2026-0001"])     # restore: legacy-auth cluster
    strengthen = engine.risk_reduction(by_id["REM-2026-0005"])  # strengthen: data-residency
    assert restore is not None and restore.low > 0
    assert strengthen is not None and strengthen.low > 0


def test_exposure_arc_bands(built):
    _, config, engine = built
    entering = engine.date_filtered_portfolio_band(config.year_start)
    current = engine.portfolio_residual_band()
    exiting = engine.post_remediation_portfolio_band()
    assert entering.mean < current.mean  # 2026 acceptances pushed the book up
    assert exiting.mean < current.mean    # the funded plan pulls it down


def test_report_renders_exposure_arc(built):
    corpus, config, engine = built
    from risk_ledger.render import fmt_band
    from risk_ledger.report import render_report

    text = render_report(engine, corpus, config)
    assert "## 2026 risk exposure" in text
    # The section names both ends of the arc: the entering band and the exiting
    # (post-funded-plan) band.
    entering = engine.date_filtered_portfolio_band(config.year_start)
    exiting = engine.post_remediation_portfolio_band()
    assert fmt_band(entering) in text
    assert fmt_band(exiting) in text


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
