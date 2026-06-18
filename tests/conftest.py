"""Shared test builders.

Most tests construct a :class:`Corpus` directly via these helpers rather than
touching the filesystem, so they are fast and explicit about the one thing under
test.
"""

from __future__ import annotations

import datetime as dt

import pytest

from risk_ledger.config import Config
from risk_ledger.loader import Corpus
from risk_ledger.models import Estimator, Exception_, Remediation, Risk

AS_OF = dt.date(2026, 6, 18)


@pytest.fixture
def config() -> Config:
    # Fewer iterations keep tests fast; the seed keeps them deterministic.
    return Config(iterations=4000, seed=7, refresh_window_days=365, as_of=AS_OF)


def make_risk(rid="RISK-X", cf=(10, 40), poa=(0.005, 0.02), lm=(200000, 500000), appetite=500000) -> Risk:
    return Risk.parse(
        rid,
        {
            "title": rid,
            "baseline": {
                "opportunity_frequency_90ci": list(cf),
                "probability_of_realization_90ci": list(poa),
                "loss_magnitude_90ci": list(lm),
            },
            "appetite_threshold": appetite,
        },
    )


def make_estimator(email="r.chen@company.com", calibrated=True, calibrated_on="2026-03-15") -> Estimator:
    return Estimator.parse(email, {"calibrated": calibrated, "calibrated_on": calibrated_on})


def make_exc(eid="EXC-0001", **over) -> Exception_:
    """Build an exception from sensible defaults, overriding any field group."""
    raw = {
        "id": eid,
        "title": over.get("title", f"exception {eid}"),
        "owner": over.get("owner", "owner@company.com"),
        "filed_on": over.get("filed_on", "2026-05-01"),
        "okr": over.get("okr", "gcloud-migration"),
        "control": over.get("control", "CTRL-1"),
        "mapped_risk": over.get("mapped_risk", "RISK-X"),
        "exception_effect": {
            "moves": over.get("moves", "probability_of_realization"),
            "with_exception_90ci": over.get("with_exception_90ci", [0.05, 0.15]),
            "estimated_by": over.get("estimated_by", "r.chen@company.com"),
            "estimated_on": over.get("estimated_on", "2026-05-01"),
        },
        "reason": over.get("reason", "timeline"),
        "scope": over.get("scope", {"type": "enumerated", "assets": ["asset-a"]}),
        "remediation": over.get(
            "remediation",
            {"target_date": "2026-09-01", "mechanism": "enforce_sso", "reduces": "probability_of_realization"},
        ),
        "status": over.get("status", "active"),
        "expires_on": over.get("expires_on", "2026-09-01"),
        "renewals": over.get("renewals", {"count": 0, "justification_changed_last": None}),
    }
    if "reason_detail" in over:
        raw["reason_detail"] = over["reason_detail"]
    return Exception_.parse(raw, path=f"{eid}.yaml")


def make_rem(rid="REM-0001", **over) -> Remediation:
    """Build a remediation from sensible defaults (restore by default)."""
    rtype = over.get("type", "restore")
    raw = {
        "id": rid,
        "title": over.get("title", f"remediation {rid}"),
        "type": rtype,
        "status": over.get("status", "funded"),
        "target_date": over.get("target_date", "2026-09-01"),
        "owner": over.get("owner", "owner@company.com"),
        "mechanism": over.get("mechanism", "do_the_thing"),
    }
    if rtype == "restore":
        raw["restores_control"] = over.get("restores_control", "CTRL-1")
    else:  # strengthen
        raw["mapped_risk"] = over.get("mapped_risk", "RISK-X")
        raw["moves"] = over.get("moves", "loss_magnitude")
        raw["post_control_90ci"] = over.get("post_control_90ci", [50000, 150000])
        raw["estimated_by"] = over.get("estimated_by", "r.chen@company.com")
        raw["estimated_on"] = over.get("estimated_on", "2026-06-01")
    for key in ("restores_control", "mapped_risk", "moves", "post_control_90ci", "estimated_by"):
        if key in over:
            raw[key] = over[key]
    return Remediation.parse(raw, path=f"{rid}.yaml")


def make_corpus(risks=None, estimators=None, exceptions=None, remediations=None) -> Corpus:
    corpus = Corpus()
    for r in risks or [make_risk()]:
        corpus.risks[r.id] = r
    for e in estimators or [make_estimator()]:
        corpus.estimators[e.email] = e
    corpus.exceptions = list(exceptions or [])
    corpus.remediations = list(remediations or [])
    return corpus
