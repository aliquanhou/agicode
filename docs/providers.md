# LLM Providers

> **Configure and switch between 5 LLM providers** — Anthropic, OpenAI, DeepSeek, Gemini, and Ollama.

---

## Supported Providers

| Provider | Models | Strengths | Cost |
|----------|--------|-----------|------|
| **Anthropic Claude** | Claude Opus 4, Sonnet 4, Haiku 4.5 | Best coding, tool use, long context | $$$ |
| **OpenAI** | GPT-4o, GPT-4o-mini | Fast, widely compatible | $$ |
| **DeepSeek** | deepseek-chat | Cost-effective, strong reasoning | $ |
| **Gemini** | gemini-pro, gemini-ultra | Google ecosystem, long context | $$ |
| **Ollama** | Local models (Llama, Mistral, etc.) | Free, offline, private | Free |

---

## Provider Setup

### 1. Anthropic Claude

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-your-key-here",
  "model": "claude-sonnet-4-20250514"
}
```

Environment variable: `ANTHROPIC_API_KEY`

Available models:
- `claude-opus-4-7` — Most capable, best for complex tasks
- `claude-sonnet-4-20250514` — Best balance of speed + quality (default)
- `claude-sonnet-4-6` — Fast Sonnet variant
- `claude-haiku-4-5` — Fastest, best for simple tasks

### 2. OpenAI

```json
{
  "provider": "openai",
  "api_key": "sk-openai-your-key",
  "model": "gpt-4o"
}
```

Environment variable: `OPENAI_API_KEY`

Available models:
- `gpt-4o` — Best overall
- `gpt-4o-mini` — Faster, cheaper

### 3. DeepSeek

```json
{
  "provider": "DeepSeek",
  "api_key": "sk-deepseek-your-key",
  "model": "deepseek-chat",
  "base_url": "https://api.deepseek.com"
}
```

Environment variable: `DEEPSEEK_API_KEY`

Available models:
- `deepseek-chat` — Default
- `deepseek-reasoner` — Reasoning model

### 4. Google Gemini

```json
{
  "provider": "gemini",
  "api_key": "AIza-your-key",
  "model": "gemini/gemini-pro"
}
```

Environment variable: `GOOGLE_API_KEY`

Available models:
- `gemini/gemini-pro` — Default
- `gemini/gemini-ultra` — Most capable

### 5. Ollama (Local)

```bash
# First, install and start Ollama
# https://ollama.ai
ollama pull llama3
```

```json
{
  "provider": "ollama",
  "model": "ollama/llama3",
  "base_url": "http://localhost:11434/v1"
}
```

No API key needed for local models.

---

## Configuration Priority

AgiCode loads configuration in this order (later sources override earlier):

1. Default values in `core.py`
2. `config.json` file
3. Environment variables
4. GUI Settings dialog

### config.json

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-sonnet-4-20250514",
  "base_url": "",
  "mcp_servers": []
}
```

### Environment Variables

```bash
# Provider credentials
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export DEEPSEEK_API_KEY=sk-...
export GOOGLE_API_KEY=AIza...

# Model selection
export LLM_MODEL=claude-sonnet-4-20250514

# Agent config
export AGICODE_MAX_TOKENS=8192
export AGICODE_MAX_ROUNDS=50
export AGICODE_DATA_DIR=/path/to/data
```

---

## Model Auto-Detection

The provider factory `create_llm_provider()` auto-detects the correct provider from the model name:

| Model Name | Provider |
|------------|----------|
| `claude-*` | Anthropic |
| `gpt-*` | OpenAI |
| `deepseek-*` | DeepSeek (via OpenAI SDK) |
| `gemini/*` | Gemini |
| `ollama/*` | Ollama (local) |
| `anthropic/*` | Anthropic (explicit prefix) |
| `openai/*` | OpenAI (explicit prefix) |

### Naming Conventions

```python
# These all work:
config = {"model": "claude-sonnet-4-20250514"}
config = {"model": "anthropic/claude-sonnet-4-20250514"}
config = {"model": "gpt-4o"}
config = {"model": "deepseek-chat"}
config = {"model": "gemini/gemini-pro"}
config = {"model": "ollama/llama3"}
```

---

## Runtime Provider Switching

You can switch providers at runtime via the GUI Settings dialog or by updating config:

```python
from agent.core import Agent

# Create agent with Anthropic
agent = Agent(config={
    "provider": "anthropic",
    "api_key": "sk-ant-...",
    "model": "claude-sonnet-4-20250514",
})

# Or switch to DeepSeek
agent = Agent(config={
    "provider": "openai",  # DeepSeek uses OpenAI SDK
    "api_key": "sk-deepseek-...",
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com/v1",
})
```

---

## Streaming Protocol

All providers support the same streaming interface:

```python
provider.stream_complete(
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Hello!"}],
    tools=[...],
    on_text=lambda delta: print(delta, end=""),
    on_tool_start=lambda name, input: print(f"\nUsing tool: {name}"),
    on_thinking=lambda delta: print(f"\033[90m{delta}\033[0m"),
)
```

Returns `{"content": "...", "tool_calls": [...]}`.

---

## Token Usage & Context Limits

| Provider | Context Window |
|----------|---------------|
| Claude Opus 4 | 200K tokens |
| Claude Sonnet 4 | 200K tokens |
| Claude Haiku 4.5 | 200K tokens |
| GPT-4o | 128K tokens |
| DeepSeek Chat | 64K tokens |
| Gemini Pro | 128K tokens |

AgiCode automatically manages context compression to stay within limits:

1. Truncates oversized tool results
2. Compacts older conversation turns
3. Drops oldest turns with summary preservation
4. Sanitizes tool_call/tool_result pairing integrity

---

*[Back to docs index](index.md)*
