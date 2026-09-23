# Risk rules (Phase 07+)

Supervisor + `RiskEngine` validate every `TradeProposal` deterministically
(max risk/exposure/positions, daily loss, symbol/session/spread limits,
mandatory SL/TP, duplicates, cooldowns, account safety).
Rejections carry explicit codes (e.g. `MAX_RISK_EXCEEDED`); silent
modification of dangerous proposals is forbidden. No risk code in Phase 00.
