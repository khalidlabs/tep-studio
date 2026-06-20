from __future__ import annotations

import argparse
from pathlib import Path

from tep_studio.simulation.validation.artifacts import DEFAULT_OUTPUT_DIR
from tep_studio.simulation.validation.runner import ValidationConfig, run_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TEP simulation validation and figure generation.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run validation scenarios.")
    run_parser.add_argument(
        "--suite",
        default="local",
        choices=["local", "adchem", "steady_state", "mat_states", "all", "r12", "mode1_short", "adchem_solver"],
    )
    run_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    run_parser.add_argument("--download-external", action="store_true")
    run_parser.add_argument("--solvers", nargs="+", default=["RK23", "RK45"])

    fig_parser = subparsers.add_parser("figures", help="Generate figures from validation outputs.")
    fig_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    report_parser = subparsers.add_parser("report", help="Generate Markdown validation report.")
    report_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_suite(
            ValidationConfig(
                suite=args.suite,
                output_dir=args.output_dir,
                solvers=tuple(args.solvers),
                download_external=bool(args.download_external),
            )
        )
        print(f"Wrote metrics for {len(result.metrics)} validation runs to {args.output_dir}")
        return 0
    if args.command == "figures":
        from tep_studio.simulation.validation.figures import generate_figures

        figures = generate_figures(args.output_dir)
        print(f"Wrote {len(figures)} figure/data files to {args.output_dir}")
        return 0
    if args.command == "report":
        from tep_studio.simulation.validation.report import generate_report

        report = generate_report(args.output_dir)
        print(f"Wrote {report}")
        return 0
    return 2
