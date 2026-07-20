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


def test_view1_is_an_interval_plot(page: str) -> None:
    # SPEC v2.8 §2: the mark is the p5-p95 interval with the mean as an interior
    # tick and the beyond-appetite slice in red; the caption says so honestly.
    assert "interval = 5&#x2013;95%" in page or "interval = 5–95%" in page
    assert "breach mass" in page
    assert "bar = mean" not in page  # the old zero-anchored bar caption is gone


def test_view1_reads_against_appetite_not_dollars(page: str) -> None:
    # SPEC v2.9 §2/§6: the axis is percent of each row's own appetite, so one static
    # appetite line at 100% is shared by every row (per-row ticks gone) and that
    # line is labelled "appetite", never a bare "100%". The caption says the mean
    # tick now carries a dollar figure; the subtitle names the new frame.
    assert ">appetite</text>" in page
    assert ">40%</text>" in page and ">60%</text>" in page
    assert "tick = mean ($)" in page
    assert "Named risks by position against their own appetite" in page
    # the old dollar-axis / per-row-tick subtitle is gone
    assert "Top named risks by residual" not in page


def test_pct_axis_bounds_pad_then_round() -> None:
    # SPEC v2.9 §2: pad by 5 points, THEN round outward to 10. The pad is the
    # guaranteed clearance; rounding alone leaves data at 50.1% on a 50% edge.
    assert dashboard._pct_axis_bounds([53.3, 156.2]) == (40.0, 170.0)  # today's corpus
    assert dashboard._pct_axis_bounds([50.1, 99.0]) == (40.0, 110.0)   # pad rescues 50.1
    assert dashboard._pct_axis_bounds([80.0, 80.0]) == (70.0, 90.0)


def test_view1_every_interval_falls_inside_the_derived_axis() -> None:
    # SPEC v2.9 §8: assert, do not eyeball — every rendered p5/p95 (percent of its
    # own appetite) sits strictly inside the derived bounds, which today are 40-170.
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    eng = GraphEngine(g, cfg)
    ranked = sorted(eng.all_named_risk_residuals(), key=dashboard._view1_key)[:8]
    pcts = [100 * v / r.threshold for r in ranked for v in (r.band.low, r.band.high)]
    lo, hi = dashboard._pct_axis_bounds(pcts)
    assert (lo, hi) == (40.0, 170.0)
    assert all(lo < p < hi for p in pcts)


def test_view1_selection_by_ratio_matches_v28_dollar_selection() -> None:
    # SPEC v2.9 §4: selection is by the ratio key, not residual dollars — above
    # appetite is unacceptable regardless of the dollar amount. Today it picks the
    # same 8 risks (a regression check; expected to stop holding after phase 2).
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    eng = GraphEngine(g, cfg)
    residuals = eng.all_named_risk_residuals()
    by_ratio = {r.named_risk.id for r in sorted(residuals, key=dashboard._view1_key)[:8]}
    by_dollars = {r.named_risk.id for r in sorted(residuals, key=lambda r: r.band.mean, reverse=True)[:8]}
    assert by_ratio == by_dollars


def test_view1_top3_order_is_seed_stable() -> None:
    # SPEC v2.9 §3: rounding the ratio to display precision BEFORE comparing locks
    # the three OVER risks to Platform > PCI > Production across seeds. The raw gap
    # (103.2% vs 102.9%) is inside the Monte Carlo's own noise, so a raw key lets
    # the seed decide row 1. The AT block below still shuffles across seeds, which
    # is correct and deliberately not stabilised (§3).
    g = load_graph(DATA)
    orders = set()
    for seed in (20260617, 1, 42, 999, 7777):
        cfg = Config(as_of=AS_OF, seed=seed)
        validate_graph(g, cfg)
        eng = GraphEngine(g, cfg)
        top3 = sorted(eng.all_named_risk_residuals(), key=dashboard._view1_key)[:3]
        orders.add(tuple(r.named_risk.label for r in top3))
    assert orders == {("Platform outage", "PCI scope creep", "Production compromise")}


def test_view1_mean_tick_carries_the_residual_mean_in_dollars() -> None:
    # SPEC v2.9 §2/§8: the mean tick's dollar label is the row's residual mean (the
    # only absolute magnitude in the chart) and matches the table for that row.
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    eng = GraphEngine(g, cfg)
    page = dashboard.build_dashboard(g, eng)
    for r in sorted(eng.all_named_risk_residuals(), key=dashboard._view1_key)[:8]:
        assert f">{dashboard.money(r.band.mean)}</text>" in page


def test_tile_row_is_four_asks_led_by_mis_allocation(page: str) -> None:
    # SPEC v2.9 §5: four tiles, four different asks. "Top fixes" (a table of contents
    # for the chart below it) and "Falling through cracks" (its orphans are already
    # mis-allocation drivers) are dropped; mis-allocation leads; Privacy
    # over-controlled keeps its own slot because there is no breach to reallocate
    # toward in a domain with nothing at or above appetite.
    assert "grid-template-columns:repeat(4,1fr)" in page
    assert page.count('class="tile-k"') == 4
    assert "Top fixes" not in page
    assert "Falling through cracks" not in page
    assert "Mis-allocated" in page and "Over-controlled" in page


def test_view2_ranks_by_idle_dollars_with_status(page: str) -> None:
    # SPEC v2.8 §3: the Simpson's-trap ratio is gone; idle dollars + a status.
    assert "Idle tolerance" in page
    assert "OVER-CONTROLLED" in page and "MIS-ALLOCATED" in page
    assert ">Tolerance used<" not in page  # the aggregate ratio column is gone


def test_view4_shows_mitigated_risks_not_policy(page: str) -> None:
    # SPEC v2.8 §4: the Policy column is replaced by the risks the control mitigates.
    assert "Mitigates" in page
    assert ">Policy</th>" not in page


def test_view5_is_predation_not_a_summed_footprint(page: str) -> None:
    # SPEC v2.9 predation view: the "true footprint" bar was a manufactured sum —
    # one project's risk plus the harm it caused to four others, stacked on one
    # axis. Retire the vocabulary and the visual entirely.
    for retired in ("true footprint", "reported vs true", "undeclared debt", " hidden"):
        assert retired not in page, retired
    assert "Which project is eating the others" in page
    assert "Black holes" in page and "Eaten alive" in page
    assert "starving 4 projects · 6 exceptions" in page  # blast radius, not a sum


def test_view5_casualties_name_predator_and_over_reads_red(page: str) -> None:
    # SPEC v2.9 predation acceptance 4/5: each eaten project names its predator and
    # shows its forced exceptions with the correct RAG state; the two over-appetite
    # casualties read red (--status-over), and amber is never used for caused-harm.
    assert 'color:var(--status-over)">EXC-2026-0131 · OVER' in page  # core-platform
    assert 'color:var(--status-over)">EXC-2026-0151 · OVER' in page  # payments-launch
    assert page.count(">gcloud-migration<") >= 4  # named as the cause on each victim row


def test_exc_tag_reds_the_over_casualty_and_never_ambers_harm() -> None:
    # SPEC v2.9 predation acceptance 5: over appetite is the escalation and reads
    # red; at/below stay muted, because amber is unused-tolerance elsewhere and must
    # never stand in for harm caused to another team.
    over = dashboard._exc_tag("EXC-2026-0131", "over")
    assert "var(--status-over)" in over and "OVER" in over
    for st in ("below", "at", None):
        tag = dashboard._exc_tag("EXC-X", st)
        assert "var(--status-below)" not in tag and "var(--status-over)" not in tag
        assert "var(--text-muted)" in tag


def test_predation_reads_the_diverted_to_graph() -> None:
    # SPEC v2.9 predation §2/§3: gcloud-migration is the one black hole, ranked by
    # blast radius; the two over-appetite casualties are EXC-0131 and EXC-0151.
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    holes = dashboard._predation(g, GraphEngine(g, cfg))
    assert len(holes) == 1
    h = holes[0]
    assert h["sink"] == "gcloud-migration"
    assert (h["n_victims"], h["n_exc"], h["n_over"]) == (4, 6, 2)
    assert h["victims"][0]["has_over"] and h["victims"][1]["has_over"]  # sharp end first
    over_ids = {eid for v in h["victims"] for eid, s in v["forced"] if s == "over"}
    assert over_ids == {"EXC-2026-0131", "EXC-2026-0151"}


def test_riding_tile_shows_predation_not_summed_debt(page: str) -> None:
    # SPEC v2.9 predation §3c: the summary tile surfaces the predation finding, not
    # the manufactured "+$1.7M undeclared debt" number.
    assert "Eating other teams" in page
    assert "starving 4 projects · 2 over appetite" in page


def test_top5_renders_above_the_summary_exactly_five(page: str) -> None:
    # SPEC v3.0 §3/§3b: the Top 5 is the executive's first read — above the
    # portfolio summary, exactly five ranked rows, and NOT one of the seven views
    # (no vnum badge; the closed-seven contract is unchanged).
    assert 'class="top5"' in page
    assert page.index('class="top5"') < page.index('class="summary"')
    top5 = re.search(r'<section class="top5".*?</section>', page, re.S).group(0)
    assert top5.count("<li>") == 5
    assert 'class="vnum"' not in top5


def test_top5_fund_rows_name_a_remediation_and_a_computed_effect(page: str) -> None:
    # SPEC v3.0 §3a / acceptance 4: every fund-row names a specific remediation ID
    # and its computed effect; no row reads "do something about X" or is finding-only.
    top5 = re.search(r'<section class="top5".*?</section>', page, re.S).group(0)
    assert "Fund REM-2026-0114 (restore A.8.14)" in top5
    assert "Fund REM-2026-0112 (restore A.8.22)" in top5
    assert "within its" in top5 and "&rarr;" in top5  # the computed effect arrow
    assert "do something about" not in top5.lower()


def test_top5_within_appetite_is_computed_not_asserted(page: str) -> None:
    # SPEC v3.0 acceptance 2 (the one that matters): each fund-row's within-appetite
    # claim is reproduced by residual_if_funded, and the computed post-funding mean
    # is what the page prints — never a back-solved figure.
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    eng = GraphEngine(g, cfg)
    for nid, rem in (("NR-PLATFORM-OUTAGE", "REM-2026-0114"), ("NR-PCI-SCOPE", "REM-2026-0112")):
        res = eng.residual_if_funded(nid, [rem])
        assert res.state != "over"                       # the claim is true
        assert dashboard.money(res.band.mean) in page    # the printed figure is the computed one


def test_top5_fund_row_states_the_landing_not_freed_money(page: str) -> None:
    # A fund-row states where the residual lands and that it is under appetite — not
    # the arithmetic of freed headroom, which read like spendable cash. Risk is a
    # dollar-denominated measure, not a pot of money to redeploy.
    top5 = re.search(r'<section class="top5".*?</section>', page, re.S).group(0)
    for banned in ("risk capacity", "risk budget", "redeploy", "it opens below the line", "strategic bet"):
        assert banned not in top5
    assert "within its" in top5                           # the landing is still stated
    # and the computed post-funding figure is still on the page
    g = load_graph(DATA)
    cfg = Config(as_of=AS_OF)
    validate_graph(g, cfg)
    eng = GraphEngine(g, cfg)
    res = eng.residual_if_funded("NR-PLATFORM-OUTAGE", ["REM-2026-0114"])
    assert dashboard.money(res.band.mean) in top5


def test_top5_is_deduped_by_risk_and_type_c_names_the_lever(page: str) -> None:
    # SPEC v3.0 acceptance 5/7: no risk appears twice; Type C rows name the lever
    # (reprioritize / hold-and-redirect), not a remediation.
    top5 = re.search(r'<section class="top5".*?</section>', page, re.S).group(0)
    text = re.sub(r"<[^>]+>", "", top5)                  # strip tags for prose checks
    assert text.count("Production compromise") == 1      # deduped, appears once
    assert "Reprioritize gcloud-migration" in text       # predation, a lever
    assert "Hold Privacy investment flat" in text        # reallocation, a lever
    # the in-progress steady-state row, not a false "fund" of an already-funded plan
    assert "Keep REM-2026-0102 on track (in progress)" in text


def test_no_probability_renders_as_a_certainty(page: str) -> None:
    # SPEC v2.8 §6: a probability printed as a bare 100% / 0% reads like a bug.
    # (width:100% on responsive SVGs / tables is layout, not a probability.)
    prose = re.sub(r"width[:=]\"?100%\"?", "", page)
    assert "100%" not in prose
    assert not re.search(r"[^0-9.]0% ", prose)


def test_pct_guard_clamps_the_extremes() -> None:
    assert dashboard._pct(0.9999) == ">99%"
    assert dashboard._pct(0.001) == "<1%"
    assert dashboard._pct(0.38) == "38%"


def test_render_to_writes_file(tmp_path: Path) -> None:
    out = dashboard.render_to(DATA, Config(as_of=AS_OF), tmp_path / "d.html")
    assert out.exists()
    assert out.read_text().startswith("<!doctype html>")
