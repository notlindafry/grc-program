"""Command-line interface.

    risk-ledger validate [--data DIR]      run the honesty gates; non-zero exit on errors
    risk-ledger drift [OKR]                per-OKR drift lens
    risk-ledger appetite [RISK]            per-risk appetite-breach lens
    risk-ledger ranked                     the ranked action list
    risk-ledger renewals                   persistence: 'temporary forever' exceptions
    risk-ledger report                     the full narrative report

Global options pin the Monte Carlo run and the calibration window; they override
any config.yaml in the corpus.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .config import Config
from .engine import Engine
from .graph import Graph
from .graph_engine import GraphEngine
from .loader import Corpus, load_corpus, load_graph
from .render import fmt_band, fmt_money
from .report import render_report
from .validation import validate_corpus, validate_graph
from .views.appetite import render_appetite
from .views.drift import render_drift
from .views.ranked import render_ranked
from .views.renewals import render_renewals


def _build_config(args: argparse.Namespace, data_dir: Path) -> Config:
    cfg = Config.load(data_dir)
    if args.iterations is not None:
        cfg.iterations = args.iterations
    if args.seed is not None:
        cfg.seed = args.seed
    if args.refresh_window is not None:
        cfg.refresh_window_days = args.refresh_window
    if args.final_stretch_weeks is not None:
        cfg.final_stretch_weeks = args.final_stretch_weeks
    if args.single_acceptance_share is not None:
        cfg.single_acceptance_share = args.single_acceptance_share
    if args.as_of is not None:
        cfg.as_of = dt.date.fromisoformat(args.as_of)
    cfg.__post_init__()  # re-validate after CLI overrides
    return cfg


def _prepare(args: argparse.Namespace) -> tuple[Corpus, Config, dict, Engine]:
    data_dir = Path(args.data)
    cfg = _build_config(args, data_dir)
    corpus = load_corpus(data_dir)
    risk_issues = validate_corpus(corpus, cfg)
    engine = Engine(corpus, cfg)
    return corpus, cfg, risk_issues, engine


def _cmd_validate(args: argparse.Namespace) -> int:
    data_dir = Path(args.data)
    cfg = _build_config(args, data_dir)
    corpus = load_corpus(data_dir)
    risk_issues = validate_corpus(corpus, cfg)

    print("# Validation\n")
    hard = 0

    if corpus.load_errors:
        # The loader only records genuinely problematic files (a missing optional
        # register is silent), so every load error is fatal.
        print("## Load errors\n")
        for msg in corpus.load_errors:
            hard += 1
            print(f"- [ERROR] {msg}")
        print()

    if risk_issues:
        print("## Risk register\n")
        for rid, issues in risk_issues.items():
            for issue in issues:
                hard += 1
                print(f"- [ERROR] {issue.message}")
        print()

    errors = [(e, e.errors) for e in corpus.exceptions if e.errors]
    flags = [(e, e.flags) for e in corpus.exceptions if e.flags and not e.errors]

    if errors:
        print("## Rejected (hard errors)\n")
        for e, issues in errors:
            hard += len(issues)
            for issue in issues:
                print(f"- [ERROR] {issue.message}")
        print()

    if flags:
        print("## Flagged (kept, handled specially)\n")
        for e, issues in flags:
            for issue in issues:
                cat = issue.category.upper()
                print(f"- [{cat} FLAG] {issue.message}")
        print()

    rem_errors = [(r, r.errors) for r in corpus.remediations if r.errors]
    rem_flags = [(r, r.flags) for r in corpus.remediations if r.flags and not r.errors]
    if rem_errors or rem_flags:
        print("## Remediations\n")
        for r, issues in rem_errors:
            hard += len(issues)
            for issue in issues:
                print(f"- [ERROR] {issue.message}")
        for r, issues in rem_flags:
            for issue in issues:
                print(f"- [{issue.category.upper()} FLAG] {issue.message}")
        print()

    total = len(corpus.exceptions)
    n_err = sum(1 for e in corpus.exceptions if e.errors)
    n_flag = sum(1 for e in corpus.exceptions if e.flags and not e.errors)
    clean = total - n_err - n_flag
    n_rem = len(corpus.remediations)
    n_rem_err = sum(1 for r in corpus.remediations if r.errors)
    print("## Summary\n")
    print(f"- {total} exception record(s)")
    print(f"- {clean} clean, {n_flag} flagged, {n_err} rejected")
    print(f"- {n_rem} remediation(s), {n_rem_err} rejected")
    if hard:
        print(f"\n{hard} hard error(s). Exit 1.")
        return 1
    print("\nNo hard errors.")
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    """Load the v2 GRC-ecosystem corpus, validate the derived graph, and print
    the SPEC §3 cardinality confirmation. Non-zero exit on any hard error."""
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


_RAG_LABEL = {"over": "OVER", "at": "AT", "below": "BELOW"}


def _prepare_graph(args: argparse.Namespace) -> tuple[Graph, Config, GraphEngine]:
    data_dir = Path(args.data)
    cfg = _build_config(args, data_dir)
    graph = load_graph(data_dir)
    validate_graph(graph, cfg)  # attach trust flags before the engine reads them
    return graph, cfg, GraphEngine(graph, cfg)


def _cmd_portfolio(args: argparse.Namespace) -> int:
    """The engine's aggregation as text: the precursor to the Day-4 dashboard.

    Rolls scenario residuals up to named risks, domains, and the portfolio;
    compares the aggregate to declared appetite and the capacity line; and
    surfaces control health, the emerging column, and KRI triggers -- kept apart
    from the appetite-tested set (SPEC §4)."""
    graph, cfg, eng = _prepare_graph(args)
    p = eng.portfolio()

    print("# Portfolio summary\n")
    if p is None:
        print("No computable managed scenarios.")
        return 0

    print("## Total residual against appetite and capacity\n")
    print(f"- Residual exposure (managed set): **{fmt_band(p.band)}**")
    if p.appetite is not None:
        verdict = "OVER — breach" if p.over_appetite else _RAG_LABEL[p.appetite_state]
        print(f"- Declared appetite {fmt_money(p.appetite)} (revenue-percent line): **{verdict}**")
    if p.capacity is not None:
        cap = "BREACHED" if p.capacity_breached else "within"
        print(f"- Capacity / materiality {fmt_money(p.capacity)} (hard line): **{cap}**")
    if p.over_appetite:
        print("\n> The bottom-up aggregate exceeds declared appetite. That is the "
              "signal: it forces remediation or an explicit, board-signed appetite increase.")

    print("\n## Your biggest exposures now (named risks, RAG-banded)\n")
    ranked = sorted(eng.all_named_risk_residuals(), key=lambda r: r.band.mean, reverse=True)
    for r in ranked[:10]:
        drivers = ", ".join(c.issue.id for c in r.drivers[:2]) or "baseline"
        print(f"- [{_RAG_LABEL[r.state]:5}] {r.named_risk.id:26} {fmt_band(r.band):>18} "
              f"(appetite {fmt_money(r.threshold)}) — driven by {drivers}")

    print("\n## Domains (monitored rollups, no per-domain ceiling)\n")
    for d in sorted(eng.all_domain_rollups(), key=lambda d: d.band.mean, reverse=True):
        print(f"- {d.domain.title:18} {fmt_band(d.band):>18}  ({len(d.named_risk_ids)} named risks)")

    print("\n## Where your safeguards are weakest (control health)\n")
    for h in eng.unhealthy_controls()[:10]:
        note = " — clean on findings, unproven (stale/missing evidence)" if h.clean_but_unproven else ""
        print(f"- [{h.health.upper():5}] {h.control.id:7} {h.control.title[:44]}{note}")

    print("\n## On the horizon (emerging — held out of the appetite math)\n")
    for e in eng.emerging_items():
        breach = "would breach appetite" if e.would_breach else "within appetite if promoted"
        vec = "/".join(e.scenario.vectors) or "—"
        print(f"- {e.scenario.id} [{vec}] {fmt_band(e.band):>18} trajectory {e.trajectory} — {breach}")
    breached = eng.breached_kris()
    if breached:
        print(f"\n- KRI triggers: {len(breached)} breached "
              f"({', '.join(k.kri_id for k in breached[:4])}{'…' if len(breached) > 4 else ''})")

    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    corpus, cfg, _, engine = _prepare(args)
    print(render_drift(engine, corpus, cfg, only_okr=args.okr))
    return 0


def _cmd_appetite(args: argparse.Namespace) -> int:
    corpus, cfg, _, engine = _prepare(args)
    print(render_appetite(engine, corpus, cfg, only_risk=args.risk))
    return 0


def _cmd_ranked(args: argparse.Namespace) -> int:
    corpus, cfg, _, engine = _prepare(args)
    print(render_ranked(engine, corpus, cfg))
    return 0


def _cmd_renewals(args: argparse.Namespace) -> int:
    corpus, cfg, _, engine = _prepare(args)
    print(render_renewals(engine, corpus, cfg))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    corpus, cfg, _, engine = _prepare(args)
    text = render_report(engine, corpus, cfg)

    if args.html:
        from .render import html_document, markdown_to_html

        out = Path(args.out) if args.out else Path("report.html")
        out.write_text(html_document(markdown_to_html(text)))
        message = f"Wrote {out}"
        if not args.no_open:
            import webbrowser

            try:
                if webbrowser.open(out.resolve().as_uri()):
                    message += " and opened it in your browser"
                else:
                    message += f" — open it by double-clicking {out}"
            except Exception:
                message += f" — open it by double-clicking {out}"
        print(message)
        return 0

    from .render import strip_raw_svg

    plain = strip_raw_svg(text)  # inline SVG is an HTML-only enhancement
    if args.out:
        Path(args.out).write_text(plain)
        print(f"Wrote {args.out}")
    else:
        print(plain)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="risk-ledger", description=__doc__)
    parser.add_argument("--data", default="data", help="corpus directory (default: data)")
    parser.add_argument("--iterations", type=int, default=None, help="Monte Carlo iterations")
    parser.add_argument("--seed", type=int, default=None, help="Monte Carlo seed")
    parser.add_argument("--refresh-window", type=int, default=None, help="calibration refresh window, days")
    parser.add_argument("--final-stretch-weeks", type=int, default=None, help="drift final-stretch window, weeks")
    parser.add_argument(
        "--single-acceptance-share",
        type=float,
        default=None,
        help="lead-contributor share (0-1) at/above which a breach is single-acceptance (default 0.5)",
    )
    parser.add_argument("--as-of", default=None, help="reference date (YYYY-MM-DD) for staleness/expiry")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="run the validation gates")

    sub.add_parser("graph", help="load the v2 ecosystem, validate the derived graph, confirm cardinalities")

    sub.add_parser("portfolio", help="the v2 engine: residual aggregation, appetite/capacity, control health, emerging")

    p_drift = sub.add_parser("drift", help="per-OKR drift view")
    p_drift.add_argument("okr", nargs="?", default=None, help="limit to one OKR")

    p_app = sub.add_parser("appetite", help="per-risk appetite-breach view")
    p_app.add_argument("risk", nargs="?", default=None, help="limit to one risk")

    sub.add_parser("ranked", help="ranked action list")

    sub.add_parser("renewals", help="persistence view: 'temporary forever' exceptions")

    p_report = sub.add_parser("report", help="full narrative report")
    p_report.add_argument("--out", default=None, help="write to a file instead of stdout")
    p_report.add_argument(
        "--html",
        action="store_true",
        help="render a formatted HTML page (default file: report.html) and open it in the browser",
    )
    p_report.add_argument(
        "--no-open",
        action="store_true",
        help="with --html, write the file but do not open a browser",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "validate": _cmd_validate,
        "graph": _cmd_graph,
        "portfolio": _cmd_portfolio,
        "drift": _cmd_drift,
        "appetite": _cmd_appetite,
        "ranked": _cmd_ranked,
        "renewals": _cmd_renewals,
        "report": _cmd_report,
    }
    try:
        return dispatch[args.command](args)
    except ValueError as exc:  # bad config / dates: fail cleanly, not with a traceback
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
