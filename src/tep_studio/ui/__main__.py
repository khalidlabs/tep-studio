"""Entry point: ``python -m tep_studio.ui`` / ``tep-ui``."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Launch the TEP Simulation Studio (Dash + Plotly).")
    parser.add_argument("--host", default="127.0.0.1", help="host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8050, help="port (default 8050)")
    parser.add_argument("--debug", action="store_true", help="run Dash in debug mode")
    args = parser.parse_args(argv)

    from tep_studio.ui import create_app

    app = create_app()
    print(f"TEP Simulation Studio running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
