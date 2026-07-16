# AgiCode Documentation

> **Glass-box Autonomous AI Agent** — Zero dead-loop, multi-LLM, MCP, sub-agent orchestration, real-time workflow visibility.

---

## 📚 Documentation Index

| Section | Description |
|---------|-------------|
| [Architecture](architecture.md) | System design, core loop, event bus, module relationships |
| [Quick Start](quickstart.md) | Installation, configuration, first run |
| [Configuration](configuration.md) | Config file, environment variables, model settings |
| [Tools Reference](tools.md) | All 40+ built-in tools with parameters and examples |
| [LLM Providers](providers.md) | Anthropic, OpenAI, DeepSeek, Gemini, Ollama setup |
| [Sub-agent System](subagents.md) | Agent definitions, isolated execution, background mode |
| [MCP Integration](mcp.md) | Connect MCP servers, auto-register tools |
| [GUI Guide](gui.md) | Desktop application features and usage |
| [Transparency System](transparency.md) | Event bus, workflow state machine, transcript protocol |
| [Development](development.md) | Contributing, testing, extending tools |
| [Security](security.md) | API key management, permission controls, best practices |

---

## Quick Links

- **GitHub**: [https://github.com/aliquanhou/agicode](https://github.com/aliquanhou/agicode)
- **License**: Apache 2.0
- **Python**: 3.10+

## Project Structure

```
AgiCode/
├── launch_gui.py           # GUI entry point
├── main.py                 # CLI entry point
├── config.json             # API keys + MCP config
│
├── agent/                  # ★ Core agent package
│   ├── core.py             #   Agent main loop (while True, transparent)
│   ├── transcript.py       #   Event bus — every step → structured events
│   ├── workflow.py         #   Workflow state machine — plan→steps→progress
│   ├── providers.py        #   LLM abstraction (5 providers)
│   ├── prompt.py           #   System prompt builder
│   ├── session.py          #   Thread-safe session state (JSONL persistence)
│   ├── context.py          #   4-stage context compression
│   ├── tools.py            #   Tool registry + type-safe dispatch
│   ├── tools_*.py          #   15 tool modules (file, shell, web, browser, ...)
│   ├── app.py              #   GUI (customtkinter, transparent)
│   ├── app_dialogs.py      #   GUI dialogs (review, research, schedule, watch)
│   ├── agent_loader.py     #   agents/*.md → Agent type registry
│   ├── tools_agent.py      #   subagent tool — isolated context execution
│   ├── mcp/client.py       #   MCP stdio client (JSON-RPC 2.0)
│   ├── tools_mcp.py        #   MCP tool — connect/discover/auto-register
│   ├── speculative.py      #   Speculative execution engine
│   ├── streaming_parser.py #   Streaming progressive parser
│   ├── file_cache.py       #   MMAP file cache
│   ├── memory.py           #   Persistent memory system
│   ├── memory_v2.py        #   Semantic memory (ChromaDB)
│   ├── agents/             #   Agent definitions (YAML frontmatter)
│   │   ├── code-architect.md
│   │   └── code-reviewer.md
│   └── plugins/            #   Plugin tools
│
├── tests/                  # 211+ tests
├── docs/                   # ★ This documentation
└── examples/               # Example outputs
```

---

*[Back to top](#agicode-documentation)*
