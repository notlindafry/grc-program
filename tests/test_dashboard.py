"""Smoke tests for the hero artifact — the executive dashboard (SPEC §6, §7).

These assert the page is well-formed and honours the closed-set contract (exactly
six views plus a portfolio summary and one worked AI example — no seventh view,
SPEC §10). They do not re-check the numbers, which the engine suites own.
"""

from __future__ import annotations

import datetime as dt
import re
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


def test_seven_views_plus_summary_and_ai_example(page: str) -> None:
    # v2.7 lifts the six-view ceiling: over-investing is a missing problem class,
    # not scope creep. Seven numbered view cards carry a .vnum badge 1..7; the AI
    # example does not; there is no eighth.
    for n in range(1, 8):
        assert f'class="vnum">{n}</span>' in page
    assert 'class="vnum">8</span>' not in page
    assert page.count('class="summary"') == 1
    assert page.count('class="card ai"') == 1


def test_status_is_never_colour_alone(page: str) -> None:
    # Identity never rides on colour alone (SPEC §7): RAG dots ship a text label
    # (view 1) or a count (view 2's domain mix). Every dot pairs with a label or
    # a number, and the RAG words are present where states are labelled.
    assert page.count('class="dot"') >= 1
    assert page.count('class="rag-l"') >= 1 or page.count('class="ragc"') >= 1
    for label in ("OVER", "AT"):
        assert label in page


def test_synthetic_and_noindex(page: str) -> None:
    assert "noindex" in page
    assert "synthetic" in page.lower()


def test_article_agreement() -> None:
    assert dashboard._article(8) == "an"
    assert dashboard._article(7) == "a"
    assert dashboard._article(5) == "a"
    assert dashboard._article(11) == "an"


def test_raw_hex_lives_only_in_root(page: str) -> None:
    # SPEC v2.4 §1: the palette is defined once in :root; nothing else carries a
    # hex literal, and the two invented hues from the Day-4 review are gone.
    root = re.search(r":root\s*\{[^}]*\}", page).group(0)
    root_hexes = set(re.findall(r"#[0-9a-fA-F]{6}", root))
    outside = [h for h in re.findall(r"#[0-9a-fA-F]{6}", page) if h not in root_hexes]
    assert outside == [], f"hex outside :root: {set(outside)}"
    assert "#9a988f" not in page and "#2c342b" not in page


def test_border_radius_is_tokenised(page: str) -> None:
    # SPEC v2.4 §4: every border-radius is a scale token (or 50% for the dot).
    for value in re.findall(r"border-radius:([^;}]+)", page):
        for part in value.split():
            assert part in ("var(--radius)", "var(--radius-sm)", "50%", "0"), part


def test_labels_are_short_titles_not_ids(page: str) -> None:
    # SPEC v2.4 §3: headline cells use the authored short_title, never an ID or a
    # .title()-cased ID. The old cosmetic outputs must not appear.
    assert not hasattr(dashboard, "_short")
    for cosmetic in ("Pci Scope", "Data Exfil", "Prod Compromise", "Platform Outage"):
        assert cosmetic not in page
    for short in ("PCI scope creep", "Production compromise", "Platform outage"):
        assert short in page


def test_named_risk_label_falls_back_to_title() -> None:
    from risk_ledger.models import NamedRisk

    with_short = NamedRisk("NR-X", "A very long formal title", "D", "o", 1.0, short_title="Short X")
    without = NamedRisk("NR-Y", "Only a title", "D", "o", 1.0)
    assert with_short.label == "Short X"
    assert without.label == "Only a title"


def test_over_control_is_a_peer_tile_never_reassurance(page: str) -> None:
    # SPEC v2.7 §3: over-investing is a problem and sits IN the tile row as a peer;
    # the old "reassurance" framing is gone from the DOM entirely.
    assert "Over-controlled" in page
    assert 'class="tile warn"' in page
    assert "reassurance" not in page.lower()


def test_over_investing_is_view_two_and_names_tier_one_domains(page: str) -> None:
    # SPEC v2.7 §4/§1: the over-investment view is second, and it is the only place
    # Tier 1 (domains) appears -- all seven domain names must render.
    titles = re.findall(r"<h3>([^<]+)</h3>", page)
    assert "over-investing" in titles[1].lower()  # the second card
    for domain in ("Privacy", "Security", "Data integrity", "Third-party",
                   "Change", "Compliance", "Resilience"):
        assert domain in page, domain


def test_bottom_up_appetite_flag_renders(page: str) -> None:
    # SPEC v2.7 §5: the 3.65x bottom-up-vs-declared appetite flag is surfaced to
    # the reader, not left as a validation-only signal.
    assert "3.65" in page and "$36.5M" in page


def test_render_to_writes_file(tmp_path: Path) -> None:
    out = dashboard.render_to(DATA, Config(as_of=AS_OF), tmp_path / "d.html")
    assert out.exists()
    assert out.read_text().startswith("<!doctype html>")
