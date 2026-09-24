"""Read-only MT5 status probe (Phase 01). Never trades, never sends orders."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.application.connection_service import ConnectionService, RetryPolicy
from mt5_agent.config.loader import load_settings
from mt5_agent.domain.terminal import MT5Credentials
from mt5_agent.infrastructure.mt5.connection_adapter import MT5ConnectionAdapter
from mt5_agent.logging_utils import configure_logging, get_logger


def _credentials_from_env(settings: object) -> MT5Credentials | None:
    login_raw = os.getenv("MT5_AGENT_MT5_LOGIN") or str(getattr(settings, "mt5_login", "") or "")
    password = os.getenv("MT5_AGENT_MT5_PASSWORD", "")
    server = os.getenv("MT5_AGENT_MT5_SERVER") or str(getattr(settings, "mt5_server", "") or "")
    if login_raw.strip() and password and server.strip():
        return MT5Credentials(login=int(login_raw), password=password, server=server)
    return None


def main() -> int:
    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_mt5")
    svc = ConnectionService(MT5ConnectionAdapter(), RetryPolicy(max_attempts=2, delay_seconds=1.0))
    try:
        health = svc.ensure_connected(
            settings.to_connection_config(), _credentials_from_env(settings)
        )
    except Exception as exc:
        logger.warning("mt5 connection failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"connected": False, "error": str(exc)}, indent=2))
        return 1
    try:
        terminal = svc.get_terminal()
        try:
            account = svc.get_account()
            account_dict = {
                "server": account.server,
                "currency": account.currency,
                "balance": account.balance,
                "equity": account.equity,
                "profit": account.profit,
            }
        except Exception as exc:
            account_dict = {"error": str(exc)}
        print(
            json.dumps(
                {
                    "connected": health.connected,
                    "trade_allowed": health.trade_allowed,
                    "terminal": {
                        "company": terminal.company,
                        "name": terminal.name,
                        "connected": terminal.connected,
                        "trade_allowed": terminal.trade_allowed,
                        "build": terminal.build,
                    },
                    "account": account_dict,
                },
                indent=2,
            )
        )
        return 0 if health.connected else 1
    finally:
        svc.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
