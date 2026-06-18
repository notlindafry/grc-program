"""Remediations: schema/validation gates and post-remediation quantification."""

from __future__ import annotations

from conftest import make_corpus, make_estimator, make_exc, make_rem, make_risk

from risk_ledger.engine import Engine
from risk_ledger.validation import validate_corpus


def _codes(rem):
    return {i.code for i in rem.issues}


def _engine(corpus, config) -> Engine:
    validate_corpus(corpus, config)
    return Engine(corpus, config)


# -- validation ---------------------------------------------------------------


def test_clean_restore_and_strengthen_pass(config):
    exc = make_exc(eid="E1", control="CTRL-1", with_exception_90ci=[0.05, 0.12])
    restore = make_rem("REM-R", type="restore", restores_control="CTRL-1")
    strengthen = make_rem("REM-S", type="strengthen", mapped_risk="RISK-X",
                          moves="loss_magnitude", post_control_90ci=[50000, 150000])
    corpus = make_corpus(exceptions=[exc], remediations=[restore, strengthen])
    validate_corpus(corpus, config)
    assert restore.issues == [] and strengthen.issues == []
    assert restore.is_funded and strengthen.counts_in_bands


def test_restore_requires_known_control(config):
    exc = make_exc(eid="E1", control="CTRL-1")
    missing = make_rem("REM-M", type="restore", restores_control="")
    unknown = make_rem("REM-U", type="restore", restores_control="CTRL-NOPE")
    corpus = make_corpus(exceptions=[exc], remediations=[missing, unknown])
    validate_corpus(corpus, config)
    assert "rem_restores_control_missing" in _codes(missing)
    assert "rem_restores_control_unknown" in _codes(unknown)
    assert missing.rejected and unknown.rejected


def test_strengthen_requires_its_fields(config):
    bad = make_rem("REM-B", type="strengthen", mapped_risk="RISK-NOPE",
                   moves="loss_magnitude", post_control_90ci=[50000, 150000])
    corpus = make_corpus(remediations=[bad])
    validate_corpus(corpus, config)
    assert "rem_mapped_risk_unknown" in _codes(bad)


def test_strengthen_uncalibrated_estimator_held_out(config):
    rem = make_rem("REM-X", type="strengthen", mapped_risk="RISK-X",
                   moves="loss_magnitude", post_control_90ci=[50000, 150000],
                   estimated_by="u@company.com")
    corpus = make_corpus(
        estimators=[make_estimator(), make_estimator("u@company.com", calibrated=False, calibrated_on=None)],
        remediations=[rem],
    )
    validate_corpus(corpus, config)
    assert "estimator_uncalibrated" in _codes(rem)
    assert rem.is_computable and not rem.counts_in_bands  # held out of trusted bands


def test_bad_type_and_status_rejected(config):
    rem = make_rem("REM-Z", type="teleport", status="someday", restores_control="CTRL-1")
    exc = make_exc(eid="E1", control="CTRL-1")
    corpus = make_corpus(exceptions=[exc], remediations=[rem])
    validate_corpus(corpus, config)
    assert "rem_type_invalid" in _codes(rem) and "rem_status_invalid" in _codes(rem)


# -- engine: post-remediation -------------------------------------------------


def test_restore_clears_its_exceptions(config):
    # Three worsening exceptions push RISK-X over; a funded restore clears them.
    excs = [make_exc(eid=f"E{i}", control="CTRL-1", with_exception_90ci=[0.15, 0.45]) for i in range(3)]
    restore = make_rem("REM-R", type="restore", restores_control="CTRL-1")
    corpus = make_corpus(exceptions=excs, remediations=[restore])
    eng = _engine(corpus, config)
    assert eng.residual("RISK-X").state == "over"
    post = eng.post_remediation_residual("RISK-X")
    assert post.state == "within"               # cleared back to baseline
    assert post.band.mean < eng.residual("RISK-X").band.mean


def test_proposed_restore_does_not_count(config):
    excs = [make_exc(eid=f"E{i}", control="CTRL-1", with_exception_90ci=[0.15, 0.45]) for i in range(3)]
    proposed = make_rem("REM-P", type="restore", restores_control="CTRL-1", status="proposed")
    corpus = make_corpus(exceptions=excs, remediations=[proposed])
    eng = _engine(corpus, config)
    # Not funded -> post-remediation residual equals current residual.
    assert eng.post_remediation_residual("RISK-X").state == eng.residual("RISK-X").state == "over"


def test_strengthen_swaps_factor_and_reduces(config):
    # No exceptions; a funded strengthen moves loss_magnitude well below baseline.
    risk = make_risk("RISK-X", lm=(400000, 900000), appetite=500000)
    rem = make_rem("REM-S", type="strengthen", mapped_risk="RISK-X",
                   moves="loss_magnitude", post_control_90ci=[50000, 120000])
    corpus = make_corpus(risks=[risk], exceptions=[], remediations=[rem])
    eng = _engine(corpus, config)
    post = eng.post_remediation_residual("RISK-X")
    assert post.band.mean < eng.residual("RISK-X").band.mean
    reduction = eng.risk_reduction(rem)
    assert reduction is not None and reduction.low > 0  # whole band buys down risk


def test_risk_reduction_for_restore_is_cleared_contribution(config):
    excs = [make_exc(eid=f"E{i}", control="CTRL-1", with_exception_90ci=[0.15, 0.45]) for i in range(2)]
    restore = make_rem("REM-R", type="restore", restores_control="CTRL-1")
    corpus = make_corpus(exceptions=excs, remediations=[restore])
    eng = _engine(corpus, config)
    reduction = eng.risk_reduction(restore)
    cluster = eng.combined_band([e.id for e in excs])
    assert reduction is not None
    assert reduction.mean == cluster.mean  # exactly the cleared cluster's contribution


def test_date_filtered_portfolio_excludes_later_filings(config):
    import datetime as dt

    early = make_exc(eid="EARLY", filed_on="2025-06-01", with_exception_90ci=[0.05, 0.12])
    late = make_exc(eid="LATE", filed_on="2026-03-01", with_exception_90ci=[0.05, 0.12])
    corpus = make_corpus(exceptions=[early, late])
    eng = _engine(corpus, config)
    entering = eng.date_filtered_portfolio_band(dt.date(2026, 1, 1))
    current = eng.portfolio_residual_band()
    assert entering.mean < current.mean  # the 2026-filed exception is excluded entering
