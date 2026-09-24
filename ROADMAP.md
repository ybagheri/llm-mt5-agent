# Roadmap

Lifecycle: `OBSERVE → CONTEXT → STRATEGY → MEMORY → PLAN → SUPERVISE → EXECUTE → VERIFY → MEMORY UPDATE`

| Phase | Name | Status |
|------:|------|--------|
| 00–12 | Foundation through hardening prototype | ✅ Implemented |
| 13 | Safety baseline hardening | ✅ Implemented: signal binding, fail-closed risk context, account-wide exposure, verified non-dry connection, dashboard escaping, account redaction |
| 14 | Execution durability | Planned: persistent idempotency ledger, UNKNOWN reconciliation, deal-level fills, broker filling-mode selection |
| 15 | Data freshness and recovery | Planned: source-aware candle/tick freshness, integrated reconnect, pre-submit revalidation |
| 16 | Evaluation and replay | Planned: closed-bar backtesting, spread/slippage assumptions, confidence calibration |
| 17 | Operations and release | Planned: Windows service packaging, secret scanning, SBOM, signed releases, live-trading runbook |

Order is intentional: the system must become reliable before autonomous. Live trading remains disabled by default and is not qualified for unattended real-money operation.

The current project is a technically strong demo/paper research baseline, not a claim of profitability. Detailed phase documents remain in [docs/phases/](docs/phases/), and the current operator documentation starts at [docs/architecture.md](docs/architecture.md).
