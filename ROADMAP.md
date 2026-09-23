# Roadmap

Lifecycle: `OBSERVE → CONTEXT → STRATEGY → MEMORY → PLAN → SUPERVISE → EXECUTE → VERIFY → MEMORY UPDATE`

| Phase | Name | Status |
|------:|------|--------|
| 00 | Project Foundation | ✅ Done (v0.1.0) |
| 01 | MT5 Connectivity | ✅ Done (v0.2.0) |
| 02 | Market Data Layer | ✅ Done (v0.3.0) |
| 03 | Account, Orders, Positions, History | ✅ Done (v0.4.0) |
| 04 | Strategy Engine | ⬜ Planned |
| 05 | LLM Provider Layer | ⬜ Planned |
| 06 | Planner | ⬜ Planned |
| 07 | Supervisor and Risk Engine | ⬜ Planned |
| 08 | Execution Engine | ⬜ Planned |
| 09 | Memory System | ⬜ Planned |
| 10 | Agent Orchestrator | ⬜ Planned |
| 11 | Dashboard (read-only) | ⬜ Planned |
| 12 | Production Hardening | ⬜ Planned |

Order is intentional: the system must become **reliable before autonomous**.
Live trading stays disabled until Phase 12 hardening + explicit opt-in.

Details per phase: [docs/phases/](docs/phases/)
