# Phase 05 — LLM Provider Layer

## Objective
Provide a provider-agnostic LLM interface with interchangeable adapters
(Gemini, OpenAI, DeepSeek, Ollama), structured (JSON) output, and full
observability (latency, tokens, model, provider, errors) — with zero SDK
dependencies and no hard-coded vendor selection.

## Scope
In scope: `LLMRequest/LLMResponse/LLMUsage/LLMMessage` models, `LLMProvider`
ABC, error taxonomy, stdlib HTTP transport, three adapter classes covering
four vendors, settings-driven factory, unit tests on fake transports, gated
live test, `scripts/check_llm.py`.
Out of scope: planning/prompts (Phase 06), trading use of LLM output.

## Architecture
```
ai/
  models.py        # LLMMessage/LLMRequest/LLMResponse/LLMUsage (no SDKs)
  provider.py      # LLMProvider ABC (generate/close)
  errors.py        # LLMError/...Configuration/...Provider/...Timeout/...Parse
  http.py          # HttpClient protocol + UrllibHttpClient (stdlib)
  shared.py        # timing, envelope decode, structured-JSON parse
  openai_compat.py # OpenAICompatibleProvider (openai/deepseek/ollama presets)
  gemini.py        # GeminiProvider (generateContent REST)
  factory.py       # create_provider()/provider_from_settings()
```
Callers depend on `LLMProvider`; the factory maps `llm_provider` strings to
adapters. Tests inject `FakeHttp`; production uses `UrllibHttpClient`.

## Components
- `LLMRequest(messages, response_format=text|json, max_tokens?, temperature,
  extra?)` with role/content validation; `LLMResponse(text, provider, model,
  latency_ms, usage, structured?, finish_reason, raw)`.
- `OpenAICompatibleProvider(provider_name, base_url, api_key?, model,
  timeout_s, http)`: `/chat/completions` schema, `response_format`
  json_object on demand, Bearer auth only when a key exists (Ollama keyless),
  error-envelope + empty-content mapping, usage extraction.
- `GeminiProvider(api_key!, model, timeout_s, base_url, http)`: system
  instruction split, `generationConfig` (temperature/maxOutputTokens/
  response_mime_type), `x-goog-api-key` auth, `usageMetadata` mapping.
- Factory presets: openai (`api.openai.com/v1`, `gpt-4o-mini`),
  deepseek (`api.deepseek.com`, `deepseek-chat`), ollama
  (`localhost:11434/v1`, `llama3.1`, no key), gemini (`gemini-2.0-flash`);
  model/base URL/key all overridable — nothing hard-coded at call sites.

## Interfaces
- `LLMProvider.generate(request) -> LLMResponse` (raises `LLMError`)
- `LLMProvider.close()` (no-op default), `.name`, `.model`
- `create_provider(name, *, model?, api_key?, base_url?, timeout_s?, http?)`
- `provider_from_settings(settings, *, http?)`

## Data Models
See Components. `structured` holds parsed JSON for `response_format='json'`;
`usage` fields are `None` when the vendor omits them; `latency_ms` is measured
client-side per call with a monotonic clock.

## Configuration
- `config/app.yaml`: `llm_provider: none`, `llm_timeout_s`, commented model/
  base URL; key **never** in YAML.
- Env: `MT5_AGENT_LLM_PROVIDER/MODEL/API_KEY/BASE_URL/TIMEOUT_S`
  (`SUPPORTED_PROVIDERS = none, openai, deepseek, gemini, ollama`).
- `'none'` (default) raises `LLMConfigurationError` with setup guidance;
  OpenAI/DeepSeek/Gemini without key raise; Ollama works keyless for local models.
- Probe: `python scripts/check_llm.py --prompt ... [--json]`.

## Error Handling
- Misconfiguration/unknown vendor: `LLMConfigurationError` (no network hit).
- HTTP 4xx/5xx + vendor error envelopes: `LLMProviderError(provider, status)`.
- Timeouts (socket + `TimeoutError`): `LLMTimeoutError`.
- Non-JSON envelopes / bad `response_format='json'` payloads / empty content:
  `LLMParseError(provider, raw)`. Keys never appear in messages.

## Security Considerations
API keys via env only (`MT5_AGENT_LLM_API_KEY`), redacted in
`AppSettings.masked()` (`"***"`), never logged by adapters/factory/scripts.
No prompt content is persisted; live tests are manual opt-in.

## Testing Strategy
- `test_llm_models`: role/content/request validation.
- `test_llm_providers`: `FakeHttp` canned envelopes — text/usage/latency,
  structured JSON + `response_format` wire check, bad-JSON/API-error/HTTP-500/
  empty-content mapping, Ollama keyless auth, Gemini headers/URL/usage,
  factory presets + rejections, settings wiring, mask redaction.
- `test_llm_live`: gated (`MT5_AGENT_RUN_LIVE_LLM_TESTS=true` + configured
  provider), skipped otherwise; asserts non-empty text + latency.

## Acceptance Criteria
- [x] `LLMProvider` exists with independent adapters (gemini/openai/deepseek/ollama)
- [x] No hard-coded provider (factory + `LLM_PROVIDER/MODEL/API_KEY` config)
- [x] `LLMRequest/LLMResponse/LLMUsage` exist
- [x] Latency, tokens, model, provider, errors tracked
- [x] Structured output supported (`response_format='json'`, parsed `structured`)

## Definition of Done
Boxes checked; `pytest/ruff/mypy` green; diff reviewed; focused commit
`feat(phase-05): ...` pushed.

## Files Added
- `src/mt5_agent/ai/{models,provider,errors,http,shared,openai_compat,gemini,factory}.py`
- `tests/unit/{test_llm_models,test_llm_providers}.py`
- `tests/integration/test_llm_live.py`
- `scripts/check_llm.py`

## Files Modified
- `src/mt5_agent/ai/__init__.py`
- `src/mt5_agent/config/settings.py` (`llm_api_key/llm_base_url`, masked redaction)
- `config/app.yaml`, `.env.example` (LLM notes)
- `docs/ai/providers.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`,
  `pyproject.toml` (v0.6.0)

## Dependencies
None new (stdlib `urllib`; vendor SDKs deliberately avoided for testability).

## Future Work
Phase 06: `Planner`/`LLMPlanner` turning `MarketContext + signal + account +
memory` into validated `TradeProposal`s — execution still forbidden there.
