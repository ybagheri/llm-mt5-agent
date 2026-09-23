# AI providers (Phase 05+)

`ai/` will expose a provider-agnostic `LLMProvider` interface
(`LLMRequest`/`LLMResponse`/`LLMUsage` with latency/tokens/errors).
Adapters (Gemini/OpenAI/DeepSeek/Ollama) are selected via
`MT5_AGENT_LLM_PROVIDER` / `MT5_AGENT_LLM_MODEL`. No provider logic in Phase 00.
