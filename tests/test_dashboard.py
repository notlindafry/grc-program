"""Smoke tests for the hero artifact — the executive dashboard (SPEC §6, §7).

These assert the page is well-formed and honours the closed-set contract (exactly
six views plus a portfolio summary and one worked AI example — no seventh view,
SPEC §10). They do not re-check the numbers, which the engine suites own.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from risk_ledger import dashboard
from risk_ledger.config import Config
from risk_ledger.graph_engine import GraphEngine
from risk_ledger.loader import load_graph
from risk_ledger.validation import validate_graph

DATA = Path(__file__).resolve().parent.parent / "data"
AS_OF = dt.date(2026, 6, 18)


@pytest.fixture(scope="module")
def page() -> str:
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    return dashboard.build_dashboard(g, GraphEngine(g, cfg))


def test_page_is_self_contained_html(page: str) -> None:
    assert page.startswith("<!doctype html>")
    assert page.rstrip().endswith("</html>")
    # baked, not a live app: no framework script tags, no external data fetches
    assert "<script" not in page.lower()
    assert "fetch(" not in page


def test_exactly_six_views_plus_summary_and_ai_example(page: str) -> None:
    # the six numbered view cards carry a .vnum badge 1..6; the AI example does not
    for n in range(1, 7):
        assert f'class="vnum">{n}</span>' in page
    assert 'class="vnum">7</span>' not in page  # no seventh view (SPEC §10)
    assert page.count('class="summary"') == 1
    assert page.count('class="card ai"') == 1


def test_status_is_never_colour_alone(page: str) -> None:
    # every RAG indicator ships a text label beside the dot (SPEC §7 accessibility)
    assert page.count('class="dot"') >= page.count('class="rag-l"') >= 1
    for label in ("OVER", "AT", "BELOW"):
        assert label in page


def test_synthetic_and_noindex(page: str) -> None:
    assert "noindex" in page
    assert "synthetic" in page.lower()


def test_article_agreement() -> None:
    assert dashboard._article(8) == "an"
    assert dashboard._article(7) == "a"
    assert dashboard._article(5) == "a"
    assert dashboard._article(11) == "an"


def test_render_to_writes_file(tmp_path: Path) -> None:
    out = dashboard.render_to(DATA, Config(as_of=AS_OF), tmp_path / "d.html")
    assert out.exists()
    assert out.read_text().startswith("<!doctype html>")
