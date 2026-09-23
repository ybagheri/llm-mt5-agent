# AI providers

Provider-agnostic LLM access (Phase 05). Application code depends on
`LLMProvider.generate(LLMRequest) -> LLMResponse`; vendors are selected by
configuration, never by imports at call sites.

## Providers
| `MT5_AGENT_LLM_PROVIDER` | Adapter | Default model | Auth |
|---|---|---|---|
| `openai` | OpenAI-compatible `/chat/completions` | `gpt-4o-mini` | `MT5_AGENT_LLM_API_KEY` |
| `deepseek` | OpenAI-compatible | `deepseek-chat` | `MT5_AGENT_LLM_API_KEY` |
| `gemini` | `generateContent` REST | `gemini-2.0-flash` | `MT5_AGENT_LLM_API_KEY` |
| `ollama` | OpenAI-compatible @ `localhost:11434/v1` | `llama3.1` | none (local) |
| `none` (default) | — | — | raises `LLMConfigurationError` with guidance |

`MT5_AGENT_LLM_MODEL/_BASE_URL/_TIMEOUT_S` override defaults (proxies,
self-hosted gateways). No vendor SDKs — stdlib `urllib` transport with an
injectable `HttpClient` (tests use fakes).

## Usage
```powershell
$env:MT5_AGENT_LLM_PROVIDER="ollama"   # or openai/deepseek/gemini + API key
python scripts/check_llm.py --prompt "Reply with exactly: ok"
python scripts/check_llm.py --prompt "Return {""ok"": true}" --json
```
Output: provider/model/latency_ms/token usage/finish reason/text (+ parsed
`structured` for `--json`).

## Observability & errors
Every `LLMResponse` carries `provider/model/latency_ms/usage/finish_reason`.
Failures raise typed errors: `LLMConfigurationError` (setup),
`LLMProviderError(provider, status)` (API/HTTP), `LLMTimeoutError`,
`LLMParseError(provider, raw)` (bad JSON/empty content). Keys are redacted in
`AppSettings.masked()` and never logged.
