"""Command-line interface: ``tep run | dataset | ui | list | version``.

A thin terminal front-end over the same backend the web studio uses, so common
tasks need no Python. The ``run``/``dataset``/``list``/``version`` subcommands are
Dash-free; only ``tep ui`` needs Dash (install the ``ui`` extra). Examples::

    tep run --horizon 24 --idv idv_01@1.0 --setpoint production_rate=24 --out run.csv
    tep dataset --seeds 1,2,3 --horizon 12 --out dataset.csv
    tep list disturbances
    tep ui --port 8051
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence


# -- argument helpers ------------------------------------------------------
def _add_scenario_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--loop", choices=("closed", "open"), default="closed", help="control loop type (default: closed)")
    parser.add_argument("--mode", choices=("mode1", "mode2", "mode3", "mode4", "mode5", "mode6"), default="mode1", help="operating mode (default: mode1)")
    parser.add_argument("--horizon", type=float, default=12.0, help="simulated horizon in hours (default: 12)")
    parser.add_argument("--control-interval", dest="control_interval", type=float, default=0.01, help="step size in hours (default: 0.01)")
    parser.add_argument("--seed", type=float, default=None, help="measurement-noise seed for reproducibility")
    parser.add_argument("--idv", action="append", default=[], metavar="NAME[@TIME]", help="activate a disturbance, e.g. idv_01 or idv_06@2.0 (repeatable)")
    parser.add_argument("--setpoint", action="append", default=[], metavar="KEY=VALUE", help="closed-loop setpoint override (repeatable)")
    parser.add_argument("--mv", action="append", default=[], metavar="KEY=VALUE", help="open-loop manual MV value (repeatable)")
    parser.add_argument("--overrides", action="store_true", help="enable the constraint override loops")
    parser.add_argument("--no-composition", dest="no_composition", action="store_true", help="disable the slow composition trims")
    parser.add_argument("--solver", default="RK4", help="integrator: RK4 (fast, default) / Euler, or adaptive RK45 / RK23 (slower)")
    parser.add_argument("--fixed-step", dest="fixed_step", type=float, default=0.0005, metavar="H", help="RK4/Euler substep in hours (default: 0.0005)")


def _parse_idv(token: str):
    from tep_studio.analysis import DisturbanceActivation

    name, _, start = token.partition("@")
    return DisturbanceActivation(idv=name.strip(), start_time=float(start) if start else 0.0)


def _parse_kv(items: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"expected KEY=VALUE, got {item!r}")
        out[key.strip()] = float(value)
    return out


def _build_scenario(args, *, name: str = "cli"):
    from tep_studio.analysis import ScenarioConfig

    cfg = ScenarioConfig(
        name=name,
        loop_type=args.loop,
        mode=args.mode,
        horizon=args.horizon,
        control_interval=args.control_interval,
        seed=args.seed,
        disturbances=tuple(_parse_idv(x) for x in args.idv),
        setpoints=_parse_kv(args.setpoint) or None,
        manual_mvs=_parse_kv(args.mv) or None,
        enable_overrides=args.overrides,
        enable_composition=not args.no_composition,
        solver_method=args.solver,
        fixed_step=args.fixed_step,
    )
    cfg.validate()
    return cfg


def _write_dataset(runs, out, *, default_name: str) -> str:
    from tep_studio.analysis import build_dataset

    fmt = "parquet" if str(out or "").lower().endswith(".parquet") else "csv"
    payload, name = build_dataset(runs, fmt=fmt)
    path = out or name or default_name
    with open(path, "wb") as handle:
        handle.write(payload)
    return path


def _print_run_summary(run) -> None:
    status = "stabilized" if (run.truncated and not run.terminated) else ("SHUTDOWN" if run.terminated else "ended")
    print(f"run {run.run_id}: {status}  final_time={run.final_time:.2f} h  steps={run.n_steps}")
    peak = run.peak.get("reactor_pressure_max") if isinstance(run.peak, dict) else None
    if peak is not None:
        print(f"  peak reactor pressure: {peak:.1f} kPa (shutdown trip at 3000)")
    metrics = run.metrics if isinstance(run.metrics, dict) else {}
    iae = metrics.get("iae", {}) if isinstance(metrics, dict) else {}
    for key in ("reactor_level", "reactor_pressure"):
        if key in iae:
            print(f"  IAE[{key}] = {iae[key]:.3f}")


# -- subcommands -----------------------------------------------------------
def _cmd_run(args) -> int:
    from tep_studio.analysis import run_scenario

    run = run_scenario(_build_scenario(args))
    _print_run_summary(run)
    if args.out:
        print(f"  wrote dataset -> {_write_dataset([run], args.out, default_name='tep_run.csv')}")
    return 0


def _cmd_dataset(args) -> int:
    from tep_studio.analysis import BatchSpec, run_batch

    base = _build_scenario(args, name="batch")
    seeds = tuple(float(s) for s in args.seeds.split(",")) if args.seeds else (args.seed,)
    _, runs = run_batch(BatchSpec(base=base, seeds=seeds, label="cli_batch"), max_workers=args.workers)
    shutdowns = sum(1 for r in runs if r.terminated)
    print(f"ran {len(runs)} scenario(s); {shutdowns} shut down")
    print(f"wrote combined dataset ({len(runs)} runs) -> {_write_dataset(runs, args.out, default_name='tep_dataset.csv')}")
    return 0


def _cmd_ui(args) -> int:
    from tep_studio.ui import create_app

    try:
        app = create_app()
    except ModuleNotFoundError as exc:  # dash / ui extra not installed
        raise SystemExit(
            'The web UI requires the "ui" extra. Install it with:\n'
            '    pip install "tep-studio[ui]"\n'
            f"(missing dependency: {exc.name})"
        )
    print(f"TEP Simulation Studio running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def _cmd_list(args) -> int:
    import tep_studio as tep

    if args.kind == "disturbances":
        for name, desc in tep.list_disturbances():
            print(f"{name}  {desc}")
    elif args.kind == "measurements":
        for name, unit, desc in tep.list_measurements():
            print(f"{name}  [{unit}]  {desc}")
    elif args.kind == "mvs":
        for name, unit, desc in tep.list_manipulated_variables():
            print(f"{name}  [{unit}]  {desc}")
    elif args.kind == "setpoints":
        for name in tep.list_setpoints():
            print(name)
    return 0


def _cmd_benchmark(args) -> int:
    from tep_studio.simulation.benchmark import ALL_IDVS, make_fdd_benchmark

    faults = tuple(s.strip() for s in args.faults.split(",")) if args.faults else ALL_IDVS
    benchmark = make_fdd_benchmark(
        faults=faults, n_runs_per_fault=args.runs, onset_h=args.onset, horizon_h=args.horizon,
        sampling_min=args.sampling_min, mode=args.mode,
        progress=lambda frac, msg: print(f"  [{frac * 100:5.1f}%] {msg}", end="\r"),
    )
    fmt = "parquet" if str(args.out).endswith(".parquet") else ("json" if str(args.out).endswith(".json") else "csv")
    benchmark.write(args.out, fmt=fmt)
    print(f"\nwrote FDD benchmark: {len(benchmark.runs)} runs, faults={len(faults)} -> {args.out}")
    return 0


def _cmd_rl_export(args) -> int:
    from tep_studio.analysis import run_scenario
    from tep_studio.simulation.rl import to_transitions, write_transitions

    run = run_scenario(_build_scenario(args, name="rl"))
    transitions = to_transitions(run)
    fmt = "parquet" if str(args.out).endswith(".parquet") else "npz"
    write_transitions(transitions, args.out, fmt=fmt)
    print(f"wrote {transitions['obs'].shape[0]} transitions -> {args.out}")
    return 0


def _cmd_version(args) -> int:
    import tep_studio

    print(tep_studio.__version__)
    return 0


# -- entry point -----------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tep", description="Tennessee Eastman Process simulator command-line interface.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run one open/closed-loop scenario")
    _add_scenario_args(p_run)
    p_run.add_argument("--out", default=None, help="write the run trajectory to CSV/Parquet (by extension)")
    p_run.set_defaults(func=_cmd_run)

    p_dataset = sub.add_parser("dataset", help="run a multi-seed batch and export a combined dataset")
    _add_scenario_args(p_dataset)
    p_dataset.add_argument("--seeds", default=None, help="comma-separated seeds, e.g. 1,2,3")
    p_dataset.add_argument("--out", default=None, help="output dataset path (CSV/Parquet by extension)")
    p_dataset.add_argument(
        "-j", "--workers", type=int, default=None, metavar="N",
        help="parallel worker processes (default: all CPU cores; use 1 for sequential)",
    )
    p_dataset.set_defaults(func=_cmd_dataset)

    p_ui = sub.add_parser("ui", help="launch the web Simulation Studio (needs the 'ui' extra)")
    p_ui.add_argument("--host", default="127.0.0.1")
    p_ui.add_argument("--port", type=int, default=8050)
    p_ui.add_argument("--debug", action="store_true")
    p_ui.set_defaults(func=_cmd_ui)

    p_list = sub.add_parser("list", help="list variables by role")
    p_list.add_argument("kind", choices=("disturbances", "measurements", "mvs", "setpoints"))
    p_list.set_defaults(func=_cmd_list)

    p_bench = sub.add_parser("benchmark", help="generate a labeled FDD benchmark dataset (fault-free + per-IDV)")
    p_bench.add_argument("--out", required=True, help="output path (.csv/.parquet/.json)")
    p_bench.add_argument("--faults", default=None, help="comma-separated IDVs (default: all 28)")
    p_bench.add_argument("--runs", type=int, default=1, help="runs (seeds) per fault (default: 1)")
    p_bench.add_argument("--onset", type=float, default=8.0, help="fault onset time in hours (default: 8)")
    p_bench.add_argument("--horizon", type=float, default=48.0, help="run horizon in hours (default: 48)")
    p_bench.add_argument("--sampling-min", dest="sampling_min", type=float, default=3.0, help="sample period in minutes (default: 3)")
    p_bench.add_argument("--mode", choices=("mode1", "mode2", "mode3", "mode4", "mode5", "mode6"), default="mode1", help="operating mode (default: mode1)")
    p_bench.set_defaults(func=_cmd_benchmark)

    p_rl = sub.add_parser("rl-export", help="export an offline-RL transition dataset from one run")
    _add_scenario_args(p_rl)
    p_rl.add_argument("--out", required=True, help="output path (.npz/.parquet)")
    p_rl.set_defaults(func=_cmd_rl_export)

    p_version = sub.add_parser("version", help="print the installed version")
    p_version.set_defaults(func=_cmd_version)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
