# Memory design (Phase 09+)

`MemoryStore` abstraction (SQLite first, PostgreSQL-compatible later) with
short-term / trade / world / strategy scopes. Compact structured records only —
no unbounded transcript dumps. No memory code in Phase 00.
