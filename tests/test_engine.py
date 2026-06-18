"""Engine: baselines, contributions, residuals, appetite states, exclusions."""

from __future__ import annotations

from conftest import make_corpus, make_estimator, make_exc, make_risk

from risk_ledger.engine import Engine
from risk_ledger.validation import validate_corpus


def _engine(corpus, config) -> Engine:
    validate_corpus(corpus, config)
    return Engine(corpus, config)


def test_baseline_within_appetite_with_no_exceptions(config):
    corpus = make_corpus(exceptions=[])
    eng = _engine(corpus, config)
    res = eng.residual("RISK-X")
    assert res.state == "within"
    assert res.band.high < res.threshold


def test_worsening_exceptions_accumulate_over_appetite(config):
    # Many individually-tolerable PoR bumps that together breach.
    excs = [
        make_exc(eid=f"EXC-{i:04d}", with_exception_90ci=[0.012, 0.035], control="IAM-LEGACY")
        for i in range(12)
    ]
    corpus = make_corpus(exceptions=excs)
    eng = _engine(corpus, config)
    res = eng.residual("RISK-X")
    assert res.state == "over"
    assert len(res.contributors) == 12
    # No single one breaches on its own -> accumulation territory.
    assert all(eng.single_acceptance_state("RISK-X", e.id) != "over" for e in excs)


def test_single_large_exception_dominates(config):
    excs = [
        make_exc(eid="EXC-BIG", with_exception_90ci=[0.2, 0.6]),
        make_exc(eid="EXC-SMALL", with_exception_90ci=[0.01, 0.03]),
    ]
    corpus = make_corpus(exceptions=excs)
    eng = _engine(corpus, config)
    res = eng.residual("RISK-X")
    top = res.contributors[0]
    assert top.exception.id == "EXC-BIG"
    assert top.band.mean > res.contributors[1].band.mean


def test_trust_flagged_excluded_from_band_but_action_flagged_included(config):
    clean = make_exc(eid="EXC-CLEAN", with_exception_90ci=[0.05, 0.12])
    nonplan = make_exc(eid="EXC-NONPLAN", with_exception_90ci=[0.05, 0.12],
                       remediation={"reduces": "probability_of_realization"})
    uncal = make_exc(eid="EXC-UNCAL", with_exception_90ci=[0.05, 0.12],
                     estimated_by="u@company.com")
    corpus = make_corpus(
        estimators=[make_estimator(), make_estimator("u@company.com", calibrated=False, calibrated_on=None)],
        exceptions=[clean, nonplan, uncal],
    )
    eng = _engine(corpus, config)
    res = eng.residual("RISK-X")
    contributor_ids = {c.exception.id for c in res.contributors}
    assert "EXC-CLEAN" in contributor_ids
    assert "EXC-NONPLAN" in contributor_ids       # action flag still counts
    assert "EXC-UNCAL" not in contributor_ids     # trust flag excluded
    assert any(c.exception.id == "EXC-UNCAL" for c in res.untrusted)


def test_inactive_exceptions_do_not_count(config):
    active = make_exc(eid="EXC-A", with_exception_90ci=[0.05, 0.12])
    lapsed = make_exc(eid="EXC-L", with_exception_90ci=[0.2, 0.6], status="lapsed")
    corpus = make_corpus(exceptions=[active, lapsed])
    eng = _engine(corpus, config)
    res = eng.residual("RISK-X")
    assert {c.exception.id for c in res.contributors} == {"EXC-A"}


def test_portfolio_band_sums_risks(config):
    r1 = make_risk("RISK-1", appetite=500000)
    r2 = make_risk("RISK-2", appetite=500000)
    excs = [
        make_exc(eid="E1", mapped_risk="RISK-1", with_exception_90ci=[0.05, 0.12]),
        make_exc(eid="E2", mapped_risk="RISK-2", with_exception_90ci=[0.05, 0.12]),
    ]
    corpus = make_corpus(risks=[r1, r2], exceptions=excs)
    eng = _engine(corpus, config)
    total = eng.portfolio_residual_band()
    assert total.mean > eng.residual("RISK-1").band.mean
    assert eng.portfolio_appetite_total() == 1_000_000


def test_residual_is_reproducible(config):
    excs = [make_exc(eid=f"E{i}", with_exception_90ci=[0.02, 0.05]) for i in range(5)]
    a = _engine(make_corpus(exceptions=[make_exc(eid=e.id, with_exception_90ci=[0.02, 0.05]) for e in excs]), config)
    b = _engine(make_corpus(exceptions=[make_exc(eid=e.id, with_exception_90ci=[0.02, 0.05]) for e in excs]), config)
    ra, rb = a.residual("RISK-X").band, b.residual("RISK-X").band
    assert (ra.low, ra.high, ra.mean) == (rb.low, rb.high, rb.mean)
