# LLM integration

The planner uses a provider abstraction and a strict JSON contract. It receives compact market context, deterministic strategy facts, recent memory notes, and account information. It returns `BUY`, `SELL`, or `HOLD` with entry, stop, target, confidence, rationale, and optional volume.

## Safe output handling

Malformed JSON, invalid numbers, invalid bracket ordering, invalid confidence, provider failure, and signal-direction mismatch all degrade to `HOLD`. Raw model text is never passed to an execution API.

## Prompt boundaries

The system prompt says that the LLM is a planner and cannot execute orders. The deterministic supervisor enforces this rule independently. A hosted provider may receive financial and market context; review data retention, model training, endpoint security, and regional compliance before enabling it.

## Provider configuration

OpenAI-compatible providers can use the configured base URL. Ollama and LM Studio can be used through an OpenAI-compatible local endpoint. Keep API keys in environment variables or a secret manager and never log request headers or credentials.

## Uncertainty

Confidence is a model estimate, not a probability guarantee. The UI and journal describe it as relative confidence under the observed setup. Always show evidence, invalidation, risk, and warnings.
