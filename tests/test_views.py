"""The three lenses: drift split, breach classification, clustering + send-back."""

from __future__ import annotations

from conftest import make_corpus, make_estimator, make_exc, make_risk

from risk_ledger.engine import Engine
from risk_ledger.validation import validate_corpus
from risk_ledger.views.appetite import classify_breach, render_appetite
from risk_ledger.views.drift import build_footprint, render_drift
from risk_ledger.views.ranked import build_clusters, fix_first_clusters, render_ranked


def _engine(corpus, config) -> Engine:
    validate_corpus(corpus, config)
    return Engine(corpus, config)


# -- drift --------------------------------------------------------------------


def test_drift_separates_internal_from_external(config):
    internal = [make_exc(eid=f"IN{i}", initiative="gcloud-migration",
                         with_exception_90ci=[0.02, 0.05]) for i in range(3)]
    external = [
        make_exc(eid="EX1", initiative="payments-launch", reason="resource_reallocation",
                 reason_detail={"diverted_to": "gcloud-migration"}, with_exception_90ci=[0.05, 0.12]),
        make_exc(eid="EX2", initiative="data-platform", reason="resource_reallocation",
                 reason_detail={"diverted_to": "gcloud-migration"}, with_exception_90ci=[0.05, 0.12]),
    ]
    corpus = make_corpus(exceptions=internal + external)
    eng = _engine(corpus, config)
    fp = build_footprint(eng, corpus, "gcloud-migration")
    assert len(fp.internal) == 3
    assert len(fp.external) == 2
    assert set(fp.external_by_project) == {"payments-launch", "data-platform"}
    assert fp.combined_band.mean > fp.internal_band.mean  # external adds on top


def test_drift_external_invisible_without_destination(config):
    # A reallocation with no destination raises its own project's risk but is not
    # credited to any initiative's external footprint.
    orphan = make_exc(eid="ORPH", initiative="payments-launch", reason="resource_reallocation")
    corpus = make_corpus(exceptions=[orphan])
    eng = _engine(corpus, config)
    fp = build_footprint(eng, corpus, "gcloud-migration")
    assert fp.external == []


# -- appetite -----------------------------------------------------------------


def test_classify_accumulation_breach(config):
    excs = [make_exc(eid=f"A{i}", with_exception_90ci=[0.012, 0.035], control="C") for i in range(12)]
    eng = _engine(make_corpus(exceptions=excs), config)
    res = eng.residual("RISK-X")
    breach = classify_breach(eng, res)
    assert res.state == "over"
    assert breach.kind == "accumulation"
    assert breach.all_tolerable_alone
    assert breach.culprit_id is None


def test_classify_single_acceptance_breach(config):
    excs = [
        make_exc(eid="DOMINANT", with_exception_90ci=[0.15, 0.45]),
        make_exc(eid="TINY", with_exception_90ci=[0.006, 0.012]),
    ]
    eng = _engine(make_corpus(exceptions=excs), config)
    res = eng.residual("RISK-X")
    breach = classify_breach(eng, res)
    assert breach.kind == "single-acceptance"
    assert breach.culprit_id == "DOMINANT"
    assert breach.dominant_share > 0.5


def test_single_acceptance_share_threshold_is_configurable(config):
    # 12 small, evenly-sized PoA bumps: none breaches alone, the lead share is
    # small (~1/12). The classification flips purely on the threshold.
    excs = [make_exc(eid=f"A{i}", with_exception_90ci=[0.012, 0.035], control="C") for i in range(12)]
    eng = _engine(make_corpus(exceptions=excs), config)
    res = eng.residual("RISK-X")
    lead_share = classify_breach(eng, res).dominant_share
    assert lead_share < 0.5  # spread out

    config.single_acceptance_share = 0.5      # default
    assert classify_breach(eng, res).kind == "accumulation"

    config.single_acceptance_share = lead_share / 2  # below the lead share
    assert classify_breach(eng, res).kind == "single-acceptance"


# -- ranked -------------------------------------------------------------------


def test_clusters_group_by_control_and_split_malformed(config):
    members = [make_exc(eid=f"L{i}", control="IAM-LEGACY", with_exception_90ci=[0.012, 0.035])
               for i in range(4)]
    members += [make_exc(eid=f"LN{i}", control="IAM-LEGACY", with_exception_90ci=[0.012, 0.035],
                         remediation={"reduces": "probability_of_action"}) for i in range(2)]
    eng = _engine(make_corpus(exceptions=members), config)
    clusters = {c.control: c for c in build_clusters(eng, corpus_of(eng))}
    legacy = clusters["IAM-LEGACY"]
    assert len(legacy.members) == 6
    assert len(legacy.well_formed) == 4
    assert len(legacy.action_flagged) == 2


def test_fix_first_excludes_within_appetite_clusters(config):
    breaching = make_risk("RISK-HOT", appetite=500000)
    calm = make_risk("RISK-CALM", appetite=50_000_000)
    excs = [make_exc(eid=f"H{i}", mapped_risk="RISK-HOT", control="HOT",
                     with_exception_90ci=[0.05, 0.14]) for i in range(4)]
    excs += [make_exc(eid="C1", mapped_risk="RISK-CALM", control="CALM",
                      with_exception_90ci=[0.05, 0.10])]
    corpus = make_corpus(risks=[breaching, calm], exceptions=excs)
    eng = _engine(corpus, config)
    controls = {c.control for c in fix_first_clusters(eng, corpus)}
    assert "HOT" in controls
    assert "CALM" not in controls


def test_render_smoke_all_views(config):
    """The renderers must not crash on a realistic mixed corpus."""
    excs = [
        make_exc(eid="EXC-OK", with_exception_90ci=[0.05, 0.12]),
        make_exc(eid="EXC-NOPLAN", with_exception_90ci=[0.05, 0.12],
                 remediation={"reduces": "probability_of_action"}),
        make_exc(eid="EXC-EXT", initiative="payments-launch", reason="resource_reallocation",
                 reason_detail={"diverted_to": "gcloud-migration"}, with_exception_90ci=[0.05, 0.12]),
    ]
    corpus = make_corpus(exceptions=excs)
    eng = _engine(corpus, config)
    for text in (
        render_drift(eng, corpus, config),
        render_appetite(eng, corpus, config),
        render_ranked(eng, corpus, config),
    ):
        assert isinstance(text, str) and text.strip()


def corpus_of(engine: Engine):
    return engine.corpus
