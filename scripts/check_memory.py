"""Memory probe: inspect scopes or record a demo cycle (SQLite file)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mt5_agent.config.loader import load_settings  # noqa: E402
from mt5_agent.domain.memory import MemoryScope  # noqa: E402
from mt5_agent.logging_utils import configure_logging, get_logger  # noqa: E402
from mt5_agent.memory.memories import (  # noqa: E402
    ShortTermMemory,
    StrategyMemory,
    TradeMemory,
    WorldMemory,
)
from mt5_agent.memory.sqlite_store import SQLiteMemoryStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or demo the memory store.")
    parser.add_argument("--db", default=None)
    parser.add_argument("--scope", default=None, choices=[s.value for s in MemoryScope])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--demo", action="store_true", help="Record one compact demo cycle, then list."
    )
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("check_memory")
    db_path = args.db or settings.memory_db_path
    store = SQLiteMemoryStore(db_path)
    try:
        short_term = ShortTermMemory(store, keep_last=settings.memory_short_term_keep)
        trade = TradeMemory(store, keep_last=settings.memory_trade_keep)
        world = WorldMemory(store, keep_last=settings.memory_world_keep)
        strategies = StrategyMemory(store, keep_last=settings.memory_strategy_keep)
        if args.demo:
            world.note("", "demo cycle recorded")
            strategies.note(settings.mt5_default_symbol, "demo signal observed")
            trade.record_outcome(settings.mt5_default_symbol, "demo outcome", net=0.0)
        scopes = [MemoryScope(args.scope)] if args.scope else list(MemoryScope)
        memories = {
            MemoryScope.SHORT_TERM: short_term,
            MemoryScope.TRADE: trade,
            MemoryScope.WORLD: world,
            MemoryScope.STRATEGY: strategies,
        }
        print(
            json.dumps(
                {
                    scope.value: [
                        {
                            "id": r.record_id,
                            "kind": r.kind.value,
                            "symbol": r.symbol,
                            "summary": r.summary,
                            "at": r.created_at.isoformat(),
                        }
                        for r in memories[scope].recent(limit=args.limit)
                    ]
                    for scope in scopes
                },
                indent=2,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        logger.warning("memory probe failed", extra={"extra_fields": {"error": str(exc)}})
        print(json.dumps({"error": str(exc)}))
        return 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
