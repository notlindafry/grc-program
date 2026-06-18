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


def test_exposure_arc_status_rides_on_coloured_over_count_labels():
    svg = exposure_arc_svg(
        _arc_rows(), 193e6,
        axis_label="annual loss exposure ($M)",
        appetite_label="aggregate annual appetite $193M",
    )
    # 0 over -> green, the peak (2) -> red, a lesser positive (1) -> amber.
    assert 'class="rl-within" text-anchor="start">0 over appetite</text>' in svg
    assert 'class="rl-over" text-anchor="start">2 over appetite</text>' in svg
    assert 'class="rl-straddling" text-anchor="start">1 over appetite</text>' in svg


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


def test_appetite_ranges_transition_is_coloured_by_post_state():
    svg = appetite_ranges_svg(_appetite_plots())
    assert 'class="rl-over">over → still over</tspan>' in svg      # still over: red
    assert 'class="rl-within">over → within</tspan>' in svg        # cleared: green
    assert 'class="rl-within">straddling → within</tspan>' in svg  # cleared: green


def test_appetite_ranges_current_is_solid_projected_is_outline():
    svg = appetite_ranges_svg(_appetite_plots())
    # Current bar: solid fill, no stroke (realized).
    assert 'fill="#b00020"/>' in svg
    # Projected bar: light tint plus a coloured stroke (projected).
    assert 'fill="#0a7d33" fill-opacity="0.12" stroke="#0a7d33"' in svg


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
