"""Read-only dashboard HTTP app (stdlib `http.server`; GET only, no actions)."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from mt5_agent.dashboard.provider import DashboardStateProvider
from mt5_agent.domain.market import Timeframe

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def is_loopback(host: str) -> bool:
    """True when `host` binds loopback only (safe default for an unauthenticated UI)."""
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>llm-mt5-agent (read-only)</title>
<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:1.5rem;border-bottom:1px solid #ddd}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.3rem .6rem;text-align:left;font-size:.9rem}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:.5rem;background:#eee;font-size:.8rem}
.ok{background:#d9f2d9}.warn{background:#fbe3b9}.err{background:#f6c9c9}
small{color:#666}</style></head>
<body><h1>llm-mt5-agent <span class="badge">read-only</span></h1>
<p><small>Auto-refreshes every {refresh}s. No trading actions exist on this dashboard.</small></p>
<div id="app">Loading…</div>
<script>
const refresh = {refresh} * 1000;
async function load() {
  try {
    const params = new URLSearchParams(location.search);
    const res = await fetch('/api/state?' + params.toString());
    const s = await res.json();
    document.getElementById('app').innerHTML = render(s);
  } catch (e) { document.getElementById('app').innerHTML = '<p class="err">fetch failed: ' + e + '</p>'; }
}
function row(k, v) { return '<tr><td>' + k + '</td><td>' + (v === null || v === undefined ? 'n/a' : v) + '</td></tr>'; }
function section(title, rows) { return '<h2>' + title + '</h2><table>' + rows.join('') + '</table>'; }
function render(s) {
  if (s.error) return '<p class="err">Error: ' + s.error + '</p>';
  let h = '<p><span class="badge ok">v' + s.version + '</span> <span class="badge">' + s.trading_mode + '</span></p>';
  h += section('Account', [row('Login', s.account.login + ' @ ' + s.account.server), row('Balance', s.account.balance + ' ' + s.account.currency), row('Equity', s.account.equity), row('Margin', s.account.margin), row('Free margin', s.account.free_margin), row('Floating', s.account.floating_profit), row('Day P&L', s.account.day_pnl)]);
  h += section('Market', [row('Symbol', s.market.symbol + ' ' + s.market.timeframe), row('Bid/Ask', s.market.bid + ' / ' + s.market.ask), row('Spread (pt)', s.market.spread_points), row('Close', s.market.latest_close), row('Session open', s.market.session_open)]);
  h += section('Agent', [row('State', s.agent.state), row('Strategy', s.agent.strategy + ' → ' + s.agent.direction), row('Confidence', s.agent.confidence), row('Proposal', s.agent.proposal_action + ' — ' + s.agent.proposal_summary)]);
  h += section('Risk', [row('Max risk/trade', s.risk.max_risk_pct + '%'), row('Exposure', s.risk.exposure_volume + ' / ' + s.risk.max_exposure_volume), row('Positions', s.risk.open_positions + ' / ' + s.risk.max_open_positions), row('Day P&L', s.risk.day_pnl)]);
  h += section('LLM', [row('Provider', s.llm.provider + ' / ' + s.llm.model), row('Latency ms', s.llm.latency_ms), row('Tokens', s.llm.total_tokens), row('Est. cost USD', s.llm.estimated_cost_usd)]);
  const list = (items) => items.length ? items.map(i => '<tr><td>' + i.kind + '</td><td>' + i.symbol + '</td><td>' + i.summary + '</td></tr>').join('') : '<tr><td colspan="3">none</td></tr>';
  h += '<h2>Memory</h2><h3>Decisions</h3><table>' + list(s.memory.recent_decisions) + '</table><h3>Trades</h3><table>' + list(s.memory.recent_trades) + '</table><h3>Events</h3><table>' + list(s.memory.recent_events) + '</table>';
  return h;
}
load(); setInterval(load, refresh);
</script></body></html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """GET-only handler: `/`, `/api/state`, `/api/health`, `/health`; else 404/405."""

    provider: DashboardStateProvider | None = None
    health_provider: Callable[[], dict[str, Any]] | None = None
    default_symbol: str = "EURUSD"
    refresh_s: int = 15
    server_version = "llm-mt5-agent"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.info("%s %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(
                200,
                "text/html; charset=utf-8",
                _PAGE.replace("{refresh}", str(self.refresh_s)).encode(),
            )
        elif parsed.path == "/api/state":
            self._serve_state(parsed.query)
        elif parsed.path == "/api/health":
            self._serve_health()
        elif parsed.path == "/health":
            self._send(200, "application/json", b'{"ok": true}')
        else:
            self._send(404, "application/json", b'{"error": "not found"}')

    # Read-only: refuse every mutating verb explicitly.
    def do_POST(self) -> None:  # noqa: N802
        self._send(405, "application/json", b'{"error": "read-only"}')

    def do_PUT(self) -> None:  # noqa: N802
        self._send(405, "application/json", b'{"error": "read-only"}')

    def do_DELETE(self) -> None:  # noqa: N802
        self._send(405, "application/json", b'{"error": "read-only"}')

    def do_PATCH(self) -> None:  # noqa: N802
        self._send(405, "application/json", b'{"error": "read-only"}')

    def _serve_state(self, query: str) -> None:
        assert self.provider is not None
        params = parse_qs(query)
        symbol = (
            params.get("symbol", [self.default_symbol])[0] or ""
        ).strip() or self.default_symbol
        tf_name = (params.get("timeframe", ["M1"])[0] or "M1").strip().upper()
        try:
            timeframe = Timeframe(tf_name)
        except ValueError:
            self._send(
                400,
                "application/json",
                json.dumps({"error": f"unsupported timeframe: {tf_name}"}).encode(),
            )
            return
        try:
            state = self.provider.build(symbol, timeframe)
        except Exception as exc:  # never leak a traceback; report cleanly
            logger.warning("dashboard build failed: %s", exc)
            self._send(500, "application/json", json.dumps({"error": str(exc)}).encode())
            return
        self._send(200, "application/json", json.dumps(state.to_dict(), default=str).encode())

    def _serve_health(self) -> None:
        try:
            if self.health_provider is None:
                body = {"status": "UNKNOWN", "healthy": False, "components": {}}
            else:
                body = self.health_provider()
        except Exception as exc:  # health endpoint must never 500 on probe failure
            logger.warning("dashboard health build failed: %s", exc)
            body = {"status": "UNHEALTHY", "healthy": False, "error": str(exc)}
        self._send(200, "application/json", json.dumps(body, default=str).encode())

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DashboardApp:
    """Owns the server lifecycle (start/stop); binds loopback by default."""

    def __init__(
        self,
        provider: DashboardStateProvider,
        *,
        host: str = "127.0.0.1",
        port: int = 8080,
        default_symbol: str = "EURUSD",
        refresh_s: int = 15,
        health_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._provider = provider
        self._host = host
        self._port = port
        self._default_symbol = default_symbol
        self._refresh_s = refresh_s
        self._health_provider = health_provider
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        port = self._server.server_address[1] if self._server else self._port
        return f"http://{self._host}:{port}"

    def start(self) -> str:
        """Bind + serve in a background thread; returns the base URL."""
        handler = type(
            "BoundHandler",
            (DashboardHandler,),
            {
                "provider": self._provider,
                # staticmethod: plain functions as class attrs would bind `self`.
                "health_provider": (
                    staticmethod(self._health_provider)
                    if self._health_provider is not None
                    else None
                ),
                "default_symbol": self._default_symbol,
                "refresh_s": self._refresh_s,
            },
        )
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
        )
        self._thread.start()
        if not is_loopback(self._host):
            logger.warning(
                "dashboard bound to non-loopback address",
                extra={
                    "extra_fields": {
                        "url": self.url,
                        "hint": "no auth layer: bind loopback or put behind an "
                        "authenticated reverse proxy (see docs/operations/hardening.md)",
                    }
                },
            )
        logger.info("dashboard listening", extra={"extra_fields": {"url": self.url}})
        return self.url

    def stop(self) -> None:
        """Graceful shutdown (idempotent)."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None


__all__ = ["DashboardApp", "DashboardHandler", "is_loopback"]
