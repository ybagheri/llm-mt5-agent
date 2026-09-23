# Memory design

Backend-agnostic `MemoryStore` (`append/recent/count/prune`) with a stdlib
SQLite implementation today and a drop-in path to PostgreSQL tomorrow —
domain code only sees `MemoryRecord`s.

## Scopes
| Facade | Scope | Keeps | Stores |
|---|---|---|---|
| `ShortTermMemory` | `short_term` | 100 | market observations (close/bid/ask) |
| `TradeMemory` | `trade` | 500 | proposals, verdicts + codes, executions, outcomes |
| `StrategyMemory` | `strategy` | 200 | signals, analyst notes |
| `WorldMemory` | `world` | 200 | regime/account notes |

## Compactness rules
Summaries capped at 280 chars, `data` dicts whitelisted per writer (no raw
MT5/LLM envelopes, no credentials), retention pruned on every append.
Kinds map to scopes via `MemoryKind.scope()`.

## Configuration
`memory_db_path` (default `data/memory.db`) + `memory_*_keep`, all env
overridable (`MT5_AGENT_MEMORY_*`).

## Probe
```powershell
python scripts/check_memory.py --demo --limit 5
python scripts/check_memory.py --scope trade --limit 10
```
