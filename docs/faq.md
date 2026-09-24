# FAQ

### Is this an autonomous live trader?

No. The default is dry-run and live execution is disabled by default. The LLM is advisory and cannot bypass deterministic risk controls.

### Why did the MT5 probe show no order test?

The supplied Alpari Demo terminal was connected and returned market data, but Algo Trading was reported as disabled during verification. The safe result is `NOT RUN`, not a fabricated Demo execution result.

### Can I use a real account?

Do not use a real account for development. The system is not qualified for unattended real-money operation. Keep `execution_mode=dry_run` and test the risk boundary first.

### Why did a signal become HOLD?

The provider may have failed, output may be malformed, the deterministic direction may not support the action, or risk context may be incomplete. HOLD is the safe outcome.

### Where are decisions recorded?

The default local SQLite journal is `data/memory.db`. Logs and journal files can contain financial context and should be protected with OS permissions.

### Can I change the LLM provider?

Yes. Configure the provider and model through `MT5_AGENT_LLM_*` settings. The planner depends on the provider abstraction, not on a single vendor SDK.
