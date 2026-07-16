"""Command-line interface for the GRC-ecosystem model.

    risk-ledger graph        load the corpus, validate the derived graph, confirm cardinalities
    risk-ledger portfolio    residual aggregation, appetite/capacity, control health, emerging
    risk-ledger drift [OKR]  per-OKR reported-vs-true footprint (undeclared risk debt)
    risk-ledger renewals     the can-you-keep-kicking view: temporary-forever + slipped work
    risk-ledger dashboard    render the executive dashboard (the hero artifact) to HTML

Global options pin the Monte Carlo run and the calibration window; they override
any ``config.yaml`` in the corpus.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .config import Config
from .graph import Graph
from .graph_engine import GraphEngine
from .graph_views import render_drift, render_renewals
from .loader import load_graph
from .render import fmt_band, fmt_money
from .validation import validate_graph

_RAG_LABEL = {"over": "OVER", "at": "AT", "below": "BELOW"}


def _build_config(args: argparse.Namespace, data_dir: Path) -> Config:
    cfg = Config.load(data_dir)
    if args.iterations is not None:
        cfg.iterations = args.iterations
    if args.seed is not None:
        cfg.seed = args.seed
    if args.refresh_window is not None:
        cfg.refresh_window_days = args.refresh_window
    if args.as_of is not None:
        cfg.as_of = dt.date.fromisoformat(args.as_of)
    cfg.__post_init__()  # re-validate after CLI overrides
    return cfg


def _prepare(args: argparse.Namespace) -> tuple[Graph, Config, GraphEngine]:
    data_dir = Path(args.data)
    cfg = _build_config(args, data_dir)
    graph = load_graph(data_dir)
    validate_graph(graph, cfg)  # attach trust flags before the engine reads them
    return graph, cfg, GraphEngine(graph, cfg)


def _cmd_graph(args: argparse.Namespace) -> int:
    """Load the corpus, validate the derived graph, and print the SPEC §3
    cardinality confirmation. Non-zero exit on any hard error."""
    data_dir = Path(args.data)
    cfg = _build_config(args, data_dir)
    graph = load_graph(data_dir)
    problems = validate_graph(graph, cfg)

    print("# GRC ecosystem graph\n")
    hard = 0
    if graph.load_errors:
        print("## Load errors\n")
        for msg in graph.load_errors:
            hard += 1
            print(f"- [ERROR] {msg}")
        print()

    errors = [p for p in problems if p.severity == "error"]
    flags = [p for p in problems if p.severity == "flag"]
    if errors:
        print("## Rejected (hard errors)\n")
        for p in errors:
            hard += 1
            print(f"- [ERROR] {p.message}")
        print()
    if flags:
        print("## Flagged (kept, handled specially)\n")
        for p in flags:
            print(f"- [{p.category.upper()} FLAG] {p.message}")
        print()

    # Residual backstop (SPEC v2.3 §B1.2): loss exposure cannot be negative. If
    # the dominance gate holds this is empty, which is why it is worth having.
    if not errors and not graph.load_errors:
        negative = GraphEngine(graph, cfg).negative_residuals()
        if negative:
            print("## Negative residual (backstop)\n")
            for rid, band in negative:
                hard += 1
                print(f"- [ERROR] {rid}: residual band low is {fmt_money(band.low)} — "
                      f"loss exposure cannot be negative")
            print()

    summary = graph.cardinality_summary()
    print("## Entities\n")
    for name, count in summary["entities"].items():
        if isinstance(count, dict):
            inner = ", ".join(f"{k}={v}" for k, v in count.items())
            print(f"- {name}: {inner}")
        else:
            print(f"- {name}: {count}")
    print("\n## Cardinalities (SPEC §3)\n")
    for edge, status in summary["edges"].items():
        print(f"- {edge}: {status}")
    print("\n## Derivation flags\n")
    for name, count in summary["flags"].items():
        print(f"- {name}: {count}")

    if hard:
        print(f"\n{hard} hard error(s). Exit 1.")
        return 1
    print("\nNo hard errors.")
    return 0


def _cmd_portfolio(args: argparse.Namespace) -> int:
    """The engine's aggregation as text: the precursor to the dashboard. Rolls
    scenario residuals up to named risks, domains, and the portfolio; states one
    position and one exceedance probability (SPEC v2.2 §E); and surfaces control
    health, the emerging column, and KRI triggers."""
    graph, cfg, eng = _prepare(args)
    p = eng.portfolio()

    print("# Portfolio summary\n")
    if p is None:
        print("No computable managed scenarios.")
        return 0

    print("## Total residual against appetite and capacity\n")
    position = _RAG_LABEL[p.appetite_state].lower()
    line = f"- Residual **{fmt_band(p.band)}** against a {fmt_money(p.appetite)} appetite: **{position}**."
    if p.capacity is not None:
        line += (f" Roughly a **{round(p.p_over_capacity * 100)}% chance** of crossing the "
                 f"{fmt_money(p.capacity)} materiality line this year.")
    print(line)
    if p.over_appetite:
        print("\n> The bottom-up aggregate exceeds declared appetite. That is the "
              "signal: it forces remediation or an explicit, board-signed appetite increase.")

    print("\n## Your biggest exposures now (named risks, RAG-banded)\n")
    ranked = sorted(eng.all_named_risk_residuals(), key=lambda r: r.band.mean, reverse=True)
    for r in ranked[:10]:
        drivers = ", ".join(c.issue.id for c in r.drivers[:2]) or "baseline"
        print(f"- [{_RAG_LABEL[r.state]:5}] {r.named_risk.id:24} {fmt_band(r.band):>16} "
              f"(appetite {fmt_money(r.threshold)}) — driven by {drivers}")

    print("\n## Domains (monitored rollups, no per-domain ceiling)\n")
    for d in sorted(eng.all_domain_rollups(), key=lambda d: d.band.mean, reverse=True):
        amber = " — amber end to end" if d.amber_end_to_end else ""
        print(f"- {d.domain.title:18} {fmt_band(d.band):>16}  ({len(d.named_risk_ids)} named risks){amber}")

    print("\n## Where your safeguards are weakest (control health)\n")
    for h in eng.unhealthy_controls()[:10]:
        note = " — clean on findings, unproven (stale/missing evidence)" if h.clean_but_unproven else ""
        print(f"- [{h.health.upper():5}] {h.control.id:7} {h.control.title[:44]}{note}")

    print("\n## On the horizon (emerging — held out of the appetite math)\n")
    for e in eng.emerging_items():
        breach = "would breach appetite" if e.would_breach else "within appetite if promoted"
        vec = "/".join(e.scenario.vectors) or "—"
        print(f"- {e.scenario.id} [{vec}] {fmt_band(e.band):>16} trajectory {e.trajectory} — {breach}")
    breached = eng.breached_kris()
    if breached:
        print(f"\n- KRI triggers: {len(breached)} breached "
              f"({', '.join(k.kri_id for k in breached[:4])}{'…' if len(breached) > 4 else ''})")

    over_cap = eng.scenarios_over_capacity()
    if over_cap:
        print(f"\n- Board-level: {len(over_cap)} scenario(s) whose residual could cross the "
              f"{fmt_money(p.capacity)} materiality line: {', '.join(s.scenario.id for s in over_cap)}")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Render the hero artifact — the executive dashboard — to a single
    self-contained HTML page (SPEC §6, §7)."""
    from . import dashboard

    data_dir = Path(args.data)
    cfg = _build_config(args, data_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dashboard.render_to(data_dir, cfg, out)
    print(f"Wrote {out}")
    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    graph, cfg, eng = _prepare(args)
    print(render_drift(graph, eng, cfg, only_okr=args.okr))
    return 0


def _cmd_renewals(args: argparse.Namespace) -> int:
    graph, cfg, _ = _prepare(args)
    print(render_renewals(graph, cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="risk-ledger", description=__doc__)
    parser.add_argument("--data", default="data", help="corpus directory (default: data)")
    parser.add_argument("--iterations", type=int, default=None, help="Monte Carlo iterations")
    parser.add_argument("--seed", type=int, default=None, help="Monte Carlo seed")
    parser.add_argument("--refresh-window", type=int, default=None, help="calibration refresh window, days")
    parser.add_argument("--as-of", default=None, help="reference date (YYYY-MM-DD) for staleness/expiry")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("graph", help="load the corpus, validate the derived graph, confirm cardinalities")
    sub.add_parser("portfolio", help="residual aggregation, appetite/capacity, control health, emerging")
    p_drift = sub.add_parser("drift", help="per-OKR reported-vs-true footprint")
    p_drift.add_argument("okr", nargs="?", default=None, help="limit to one OKR")
    sub.add_parser("renewals", help="the can-you-keep-kicking view")
    p_dash = sub.add_parser("dashboard", help="render the executive dashboard (hero artifact) to HTML")
    p_dash.add_argument("--out", default="docs/dashboard.html", help="output path (default: docs/dashboard.html)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "graph": _cmd_graph,
        "portfolio": _cmd_portfolio,
        "drift": _cmd_drift,
        "renewals": _cmd_renewals,
        "dashboard": _cmd_dashboard,
    }
    try:
        return dispatch[args.command](args)
    except ValueError as exc:  # bad config / dates: fail cleanly, not with a traceback
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
