"""The honesty gates: every rule from the SPEC, error vs flag, trust vs action."""

from __future__ import annotations

from conftest import make_corpus, make_estimator, make_exc, make_risk

from risk_ledger.validation import validate_corpus


def _codes(exc):
    return {i.code for i in exc.issues}


def test_clean_exception_has_no_issues(config):
    exc = make_exc()
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert exc.issues == []
    assert exc.is_well_formed


def test_unknown_mapped_risk_is_a_hard_error(config):
    exc = make_exc(mapped_risk="RISK-NOPE")
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "mapped_risk_unknown" in _codes(exc)
    assert exc.rejected and not exc.is_computable


def test_missing_mapped_risk_is_rejected(config):
    exc = make_exc(mapped_risk="")
    # Exception_.parse stores "" so mapped_risk_missing fires.
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "mapped_risk_missing" in _codes(exc)
    assert exc.rejected


def test_point_estimate_rejected(config):
    exc = make_exc(with_exception_90ci=0.2)  # scalar, not a CI
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "with_exception_point_estimate" in _codes(exc)
    assert exc.rejected


def test_moves_must_name_a_real_variable(config):
    exc = make_exc(moves="vibes")
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "moves_invalid" in _codes(exc)


def test_probability_out_of_range_rejected(config):
    exc = make_exc(moves="probability_of_realization", with_exception_90ci=[0.5, 1.4])
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "with_exception_out_of_range" in _codes(exc)


def test_uncalibrated_estimator_is_a_trust_flag(config):
    corpus = make_corpus(
        estimators=[make_estimator("u@company.com", calibrated=False, calibrated_on=None)],
        exceptions=[make_exc(estimated_by="u@company.com")],
    )
    exc = corpus.exceptions[0]
    validate_corpus(corpus, config)
    assert "estimator_uncalibrated" in _codes(exc)
    assert exc.is_computable          # still computes
    assert not exc.counts_in_bands    # but not trusted into a band
    assert exc.send_back


def test_stale_estimator_is_a_trust_flag(config):
    corpus = make_corpus(
        estimators=[make_estimator("s@company.com", calibrated=True, calibrated_on="2024-01-01")],
        exceptions=[make_exc(estimated_by="s@company.com")],
    )
    exc = corpus.exceptions[0]
    validate_corpus(corpus, config)
    assert "estimator_stale" in _codes(exc)
    assert not exc.counts_in_bands


def test_unknown_estimator_treated_as_uncalibrated(config):
    exc = make_exc(estimated_by="ghost@company.com")
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "estimator_unknown" in _codes(exc)


def test_non_plan_is_an_action_flag_that_still_counts_in_bands(config):
    exc = make_exc(remediation={"reduces": "probability_of_realization"})  # no target/mechanism
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "remediation_non_plan" in _codes(exc)
    assert exc.counts_in_bands       # the number is fine
    assert not exc.is_well_formed    # but it cannot be actioned
    assert exc.send_back


def test_reallocation_requires_destination(config):
    exc = make_exc(reason="resource_reallocation")  # no reason_detail.diverted_to
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "reallocation_no_destination" in _codes(exc)
    assert exc.counts_in_bands  # action flag, number trusted


def test_reallocation_with_destination_is_clean(config):
    exc = make_exc(reason="resource_reallocation", reason_detail={"diverted_to": "gcloud-migration"})
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert exc.is_well_formed
    assert exc.diverted_to == "gcloud-migration"


def test_vague_scope_is_a_trust_flag(config):
    exc = make_exc(scope={"type": "enumerated", "assets": ["all internal systems"]})
    validate_corpus(make_corpus(exceptions=[exc]), config)
    assert "scope_vague" in _codes(exc)
    assert not exc.counts_in_bands  # vagueness corrupts the magnitude


def test_invalid_risk_baseline_rejects_its_exceptions(config):
    bad = make_risk("RISK-BAD", poa=(0.0, 0.02))  # probability low must be > 0
    exc = make_exc(mapped_risk="RISK-BAD")
    corpus = make_corpus(risks=[bad], exceptions=[exc])
    risk_issues = validate_corpus(corpus, config)
    assert "RISK-BAD" in risk_issues
    assert "mapped_risk_invalid" in _codes(exc)
