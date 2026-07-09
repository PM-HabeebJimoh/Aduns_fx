"""Command-line interface for HYDRA-PRIME."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from .acquire import PublicDataAcquirer
from .backtest import StrictRealDataBacktester
from .formatting import decision_to_json, format_pre_move_signal
from .free_sources import probe_free_sources, write_probe_report
from .live import LiveConfig, LiveOpportunityScanner
from .testing_scenarios import build_bullish_xau_engine


def cmd_demo(args: argparse.Namespace) -> int:
    engine = build_bullish_xau_engine(capital=args.capital)
    decisions = engine.evaluate(["XAUUSD"])
    if args.json:
        print(json.dumps([json.loads(decision_to_json(d)) for d in decisions], indent=2))
    else:
        for decision in decisions:
            print(format_pre_move_signal(decision, capital=args.capital))
            print()
        print("Diagnostics:")
        print(json.dumps(engine.diagnostics(), indent=2, default=str))
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.run(  # noqa: S603 - fixed Python unittest command
        [sys.executable, "-m", "unittest", "discover", "-v"],
        cwd=repo,
        text=True,
    )
    return int(proc.returncode)


def cmd_backtest(args: argparse.Namespace) -> int:
    runner = StrictRealDataBacktester(
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        strict_realtime_only=not args.allow_non_realtime_archives,
    )
    json_path, md_path, report = runner.write_report(args.report_dir)
    print(f"Status: {report.status}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    if report.blockers:
        print("Blockers:")
        for blocker in report.blockers:
            print(f"- {blocker}")
    if report.opportunity_replay is not None:
        print(json.dumps(report.opportunity_replay, indent=2))
    return 0 if report.status == "OK" else 2


def cmd_acquire(args: argparse.Namespace) -> int:
    acquirer = PublicDataAcquirer(
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        timeout=args.timeout,
    )
    symbols = [s.strip().upper() for s in args.dukascopy_symbols.split(",") if s.strip()]
    report = acquirer.run(symbols, max_dukascopy_files=args.max_dukascopy_files)
    json_path, md_path = acquirer.write_report(args.report_dir, report)
    print(f"Status: {report.status}")
    print(f"Manifest: {report.manifest_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    if report.blockers:
        print("Blockers:")
        for blocker in report.blockers:
            print(f"- {blocker}")
    return 0 if report.status == "OK" else 2


def cmd_live(args: argparse.Namespace) -> int:
    if args.config:
        config = LiveConfig.from_file(args.config)
    else:
        config = LiveConfig()
    if args.instruments:
        config.instruments = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    if args.capital is not None:
        config.capital = args.capital
    if args.interval is not None:
        config.poll_interval_seconds = args.interval
    if args.alert_log:
        config.alert_log = args.alert_log
    if args.health_report:
        config.health_report = args.health_report
    scanner = LiveOpportunityScanner(config)
    cycles = 1 if args.once else args.cycles
    scanner.run_forever(cycles=cycles)
    try:
        health = json.loads(Path(config.health_report).read_text(encoding="utf-8"))
        print(f"Health report: {config.health_report}")
        print(f"Final status: {health.get('status')}")
        return 0 if health.get("status") == "LIVE" else 2
    except Exception:
        return 1


def cmd_probe_free_sources(args: argparse.Namespace) -> int:
    report = probe_free_sources(
        start=args.start,
        end=args.end,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )
    json_path, md_path = write_probe_report(report, args.report_dir)
    print(f"Status: {report.status}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    ok = sum(1 for r in report.results if r.status == "OK")
    total = len(report.results)
    print(f"Sources OK: {ok}/{total}")
    for result in report.results:
        if result.status != "OK":
            print(f"- {result.feed}/{result.name}: {result.status} — {result.error or result.reason}")
    return 0 if report.status == "OK" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HYDRA-PRIME pre-movement decision engine")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run deterministic all-signal XAUUSD health demo")
    demo.add_argument("--capital", type=float, default=10_000.0)
    demo.add_argument("--json", action="store_true", help="Output JSON instead of text")
    demo.set_defaults(func=cmd_demo)

    test = sub.add_parser("self-test", help="Run the repository unit tests")
    test.set_defaults(func=cmd_self_test)

    live = sub.add_parser(
        "live",
        help="Run HYDRA-PRIME as a live opportunity alert scanner",
    )
    live.add_argument("--config", help="JSON config file, e.g. config/live.example.json")
    live.add_argument("--once", action="store_true", help="Run exactly one live scan cycle")
    live.add_argument("--cycles", type=int, default=None, help="Run N cycles then exit; omit for continuous mode")
    live.add_argument("--interval", type=float, default=None, help="Polling interval seconds")
    live.add_argument("--instruments", help="Comma-separated instruments, e.g. XAUUSD,EURUSD,USDJPY")
    live.add_argument("--capital", type=float, default=None, help="Capital reference for advisory trade parameters")
    live.add_argument("--alert-log", default=None, help="JSONL alert log path")
    live.add_argument("--health-report", default=None, help="Health report JSON path")
    live.set_defaults(func=cmd_live)

    probe = sub.add_parser(
        "probe-free-sources",
        help="Probe all researched free replacement data sources and write a provenance report",
    )
    probe.add_argument("--start", required=True, help="Start date, e.g. 2026-01-01")
    probe.add_argument("--end", required=True, help="End date, e.g. 2026-01-31")
    probe.add_argument("--output-dir", default="data/free_source_probes", help="Directory for probe payload samples")
    probe.add_argument("--report-dir", default="reports", help="Directory for JSON/Markdown probe reports")
    probe.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    probe.set_defaults(func=cmd_probe_free_sources)

    acquire = sub.add_parser(
        "acquire",
        help="Attempt lawful public acquisition of all HYDRA required data feeds",
    )
    acquire.add_argument("--start", required=True, help="Start date, e.g. 2026-01-01")
    acquire.add_argument("--end", required=True, help="End date, e.g. 2026-07-07")
    acquire.add_argument("--data-dir", default="data/realtime_archive", help="Directory for downloaded archives and manifest")
    acquire.add_argument("--report-dir", default="reports", help="Directory for acquisition reports")
    acquire.add_argument(
        "--dukascopy-symbols",
        default="XAUUSD,XAGUSD,EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF",
        help="Comma-separated Dukascopy symbols to download as public quote ticks",
    )
    acquire.add_argument(
        "--max-dukascopy-files",
        type=int,
        default=None,
        help="Safety cap for Dukascopy hourly files; omit for full period",
    )
    acquire.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    acquire.set_defaults(func=cmd_acquire)

    backtest = sub.add_parser(
        "backtest",
        help="Run strict real-time-archive-only opportunity-feed audit for a date range",
    )
    backtest.add_argument("--start", required=True, help="Start date, e.g. 2026-01-01")
    backtest.add_argument("--end", required=True, help="End date, e.g. 2026-07-07")
    backtest.add_argument("--data-dir", default="data/realtime_archive", help="Directory containing manifest.json and CSV archives")
    backtest.add_argument("--report-dir", default="reports", help="Directory for JSON/Markdown reports")
    backtest.add_argument(
        "--allow-non-realtime-archives",
        action="store_true",
        help="Relax provenance to allow non-realtime historical archives. Do not use for the user's strict request.",
    )
    backtest.set_defaults(func=cmd_backtest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
