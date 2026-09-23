"""Package entry-point: `python -m mt5_agent` and `mt5-agent` console script.

Phase 00 only exposes configuration/logging smoke functionality.
No trading functionality exists yet.
"""

from __future__ import annotations

import argparse
import sys

from mt5_agent import __version__
from mt5_agent.config.loader import load_settings
from mt5_agent.logging_utils import configure_logging, get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mt5-agent",
        description="AI-assisted MetaTrader 5 agent (demo-first). Phase 00: foundation only.",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit.")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML config file (default: config/app.yaml).",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override log level (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--log-format",
        default=None,
        choices=["json", "text"],
        help="Override log format.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    settings = load_settings(config_path=args.config)
    level = str(args.log_level or settings.log_level)
    fmt = str(args.log_format or settings.log_format)
    configure_logging(level=level, log_format=fmt)
    logger = get_logger(__name__)
    logger.info(
        "agent foundation initialized",
        extra={
            "extra_fields": {
                "version": __version__,
                "app_name": settings.app_name,
                "env": settings.env,
                "trading_mode": settings.trading_mode,
            }
        },
    )
    print(f"{settings.app_name} v{__version__} [{settings.env}/{settings.trading_mode}] ready.")
    print("Phase 00: foundation only — no trading functionality.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
