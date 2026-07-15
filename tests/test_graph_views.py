"""The graph-backed views ported from the retired legacy v1 (SPEC v2.2 §C1, §C2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_ledger.config import Config
from risk_ledger.graph_engine import GraphEngine
from risk_ledger.graph_views import (
    build_drift,
    flagged_renewals,
    slipped_remediations,
)
from risk_ledger.loader import load_graph
from risk_ledger.validation import validate_graph

DATA = Path(__file__).resolve().parent.parent / "data"
AS_OF = dt.date(2026, 6, 18)


@pytest.fixture(scope="module")
def built():
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    return g, cfg, GraphEngine(g, cfg)


def test_drift_shows_undeclared_debt_on_the_migration(built):
    # SPEC §C2 / §E story 7: gcloud-migration's true footprint exceeds its
    # reported one, because other OKRs' work was reallocated to fund it.
    g, _, eng = built
    d = build_drift(g, eng, "gcloud-migration")
    assert d.reported is not None and d.true is not None
    assert d.has_undeclared_debt
    assert d.true.mean > d.reported.mean            # the ledger hides carried debt
    assert len(d.diverted_in_ids) >= 3              # several reallocated exceptions


def test_drift_is_zero_where_no_debt_was_diverted(built):
    # An OKR nobody reallocated resources to has no undeclared debt gap.
    g, _, eng = built
    d = build_drift(g, eng, "observability")  # no diverted_to points here
    assert not d.has_undeclared_debt


def test_renewals_flags_temporary_forever(built):
    g, cfg, _ = built
    flagged = flagged_renewals(g, cfg)
    assert len(flagged) >= 4
    # All are renewed at least the alert count and never re-justified.
    assert all(e.renewal_count >= cfg.renewal_alert_count for e in flagged)
    assert all(not e.justification_changed_last for e in flagged)
    # Sorted most-renewed first.
    counts = [e.renewal_count for e in flagged]
    assert counts == sorted(counts, reverse=True)


def test_slipped_remediations_are_chronic_deferral(built):
    g, cfg, _ = built
    slipped = slipped_remediations(g, cfg)
    assert len(slipped) >= 10                        # real chronic deferral, not a one-off
    assert all(r.target_date < AS_OF for r in slipped)
