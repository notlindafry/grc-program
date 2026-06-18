"""The two inline charts: scaling helpers, neutral arc bars with semantic status
labels, and own-scale appetite small multiples with post-state-coloured outlines.

These assert on the generated SVG strings -- the charts are pure presentation, so
the contract is the markup they emit, not any computed value."""

from __future__ import annotations

from risk_ledger.montecarlo import Band
from risk_ledger.render_svg import (
    NEUTRAL,
    AppetitePlot,
    ArcRow,
    appetite_ranges_svg,
    compact_money,
    exposure_arc_svg,
    nice_ceiling,
    range_label,
)


def band(low: float, high: float) -> Band:
    return Band(low=low, high=high, mean=(low + high) / 2)


def test_nice_ceiling_rounds_up_to_a_clean_number():
    assert nice_ceiling(289.6e6) == 300e6  # arc max -> clean 300M
    assert nice_ceiling(214.5) == 250.0
    assert nice_ceiling(13.4) == 15.0


def test_compact_money_and_range_label():
    assert compact_money(193e6) == "$193M"  # stated figure, no decimals
    assert compact_money(5e6) == "$5M"
    assert range_label(band(119.4e6, 289.6e6)) == "$119–290M"  # the spec example
    assert range_label(band(21e6, 38e6)) == "$21–38M"


def _arc_rows():
    return [
        ArcRow("entering 2026", band(21e6, 38e6), 0),
        ArcRow("mid-year (today)", band(119e6, 290e6), 2),
        ArcRow("exiting 2026", band(69e6, 172e6), 1),
    ]


def test_exposure_arc_bars_are_neutral_not_the_semantic_ramp():
    svg = exposure_arc_svg(
        _arc_rows(), 193e6,
        axis_label="annual loss exposure ($M)",
        appetite_label="aggregate annual appetite $193M",
    )
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    # Every bar is neutral; the bars never take the over/within colours.
    assert svg.count(f'fill="{NEUTRAL}"') == 3
    assert 'fill="#b00020"' not in svg and 'fill="#0a7d33"' not in svg


def test_exposure_arc_over_count_labels_are_neutral():
    svg = exposure_arc_svg(
        _arc_rows(), 193e6,
        axis_label="annual loss exposure ($M)",
        appetite_label="aggregate annual appetite $193M",
    )
    # The counts still show (the data); their colour is neutral, not a RAG ramp.
    for count in ("0 over appetite", "1 over appetite", "2 over appetite"):
        assert f'class="rl-status" text-anchor="start">{count}</text>' in svg
    assert "rl-over" not in svg and "rl-within" not in svg and "rl-straddling" not in svg


def test_exposure_arc_annualization_on_axis_and_appetite_line():
    svg = exposure_arc_svg(
        _arc_rows(), 193e6,
        axis_label="annual loss exposure ($M)",
        appetite_label="aggregate annual appetite $193M",
    )
    assert "annual loss exposure ($M)" in svg
    assert "aggregate annual appetite $193M" in svg
    assert range_label(band(119e6, 290e6)) in svg  # each band's range printed


def _appetite_plots():
    return [
        AppetitePlot("RISK-PLATFORM-OUTAGE", band(48e6, 214e6), "over",
                     band(16e6, 117e6), "over", 15e6),
        AppetitePlot("RISK-ACCT-TAKEOVER", band(6e6, 11e6), "over",
                     band(0.5e6, 2.4e6), "within", 5e6),
        AppetitePlot("RISK-DATA-EXFIL", band(3.5e6, 13e6), "straddling",
                     band(0.45e6, 4.2e6), "within", 6e6),
    ]


def test_appetite_ranges_render_one_plot_per_breaching_risk():
    # Adapts to the data: three breaching risks -> three current/after-plan rows.
    svg = appetite_ranges_svg(_appetite_plots())
    assert svg.count(">current</text>") == 3
    assert svg.count(">after plan</text>") == 3


def test_appetite_ranges_one_plot_when_only_one_breaches():
    svg = appetite_ranges_svg(_appetite_plots()[:1])
    assert svg.count(">current</text>") == 1
    assert svg.count(">after plan</text>") == 1


def test_appetite_ranges_header_has_colon_then_tab():
    svg = appetite_ranges_svg(_appetite_plots())
    # The risk title gets a colon and a tab gap (dx) before the status.
    assert 'start">RISK-PLATFORM-OUTAGE:<tspan dx="20" class="rl-status">' in svg


def test_appetite_ranges_transition_text_kept_but_neutral():
    svg = appetite_ranges_svg(_appetite_plots())
    # The transition text (the data) is unchanged; only the colour is neutralized.
    assert 'class="rl-status">over → still over</tspan>' in svg
    assert 'class="rl-status">over → within</tspan>' in svg
    assert 'class="rl-status">straddling → within</tspan>' in svg


def test_appetite_ranges_current_is_solid_projected_is_outline():
    svg = appetite_ranges_svg(_appetite_plots())
    # Both bars are neutral blue; solid vs outline is the only distinction.
    assert f'fill="{NEUTRAL}"/>' in svg  # solid current bar, no stroke
    assert f'fill="{NEUTRAL}" fill-opacity="0.12" stroke="{NEUTRAL}"' in svg  # outline


def test_charts_carry_no_rag_colours():
    arc = exposure_arc_svg(_arc_rows(), 193e6, axis_label="annual loss exposure ($M)",
                           appetite_label="aggregate annual appetite $193M")
    app = appetite_ranges_svg(_appetite_plots())
    for svg in (arc, app):
        for rag in ("#b00020", "#b06a00", "#0a7d33"):
            assert rag not in svg
        for cls in ("rl-over", "rl-straddling", "rl-within"):
            assert cls not in svg


def test_appetite_ranges_every_appetite_line_says_annual():
    svg = appetite_ranges_svg(_appetite_plots())
    assert svg.count("annual appetite $") == 3
    assert "annual appetite $15M" in svg


def test_appetite_ranges_escapes_risk_names():
    plots = [AppetitePlot("RISK-<x>", band(6e6, 11e6), "over",
                          band(0.5e6, 2.4e6), "within", 5e6)]
    svg = appetite_ranges_svg(plots)
    assert "RISK-&lt;x&gt;" in svg  # data text is escaped even on the raw path
    assert "RISK-<x>" not in svg
