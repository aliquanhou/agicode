
<p align="center">
  <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/Tools-40%2B-orange" alt="Tools">
  <img src="https://img.shields.io/badge/Release-v1.0-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/LLM-Anthropic%20·%20OpenAI%20·%20DeepSeek%20·%20Gemini%20·%20Ollama-purple" alt="Providers">
  <img src="https://img.shields.io/badge/Status-Production%20Ready-00d4ff" alt="Status">
  <img src="https://img.shields.io/badge/Transparency-Glass%20Box-success" alt="Transparency">
</p>

<h1 align="center">AgiCode — Glass-box Autonomous AI Agent</h1>
<p align="center"><b>See every thought, every tool call, every decision — in real time.</b></p>

<p align="center">
  <a href="docs/quickstart.md">Quick Start</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/tools.md">Tools</a> ·
  <a href="docs/transparency.md">Transparency</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

> **English:** AgiCode is a **glass-box autonomous AI agent** for software engineering. Every step — thinking, tool calls, results, plan progress — is broadcast as structured events in real time on a first-of-its-kind transparent interface.
>
> **中文:** AgiCode 是一个**全透明自主 AI 工程智能体**。每一步——思考、工具调用、结果、工作流进度——都以结构化事件实时广播，用户可以看到 Agent 正在做什么、下一步计划、以及当前进度。

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔮 **Glass-box Transparency** | Every agent step → structured events (transcript bus). Users see what's happening NOW |
| 🚫 **Zero Dead-loop** | `while True` loop — model decides when to stop. No hard caps, no blocking detection |
| 🧠 **Multi-LLM Support** | 5 providers: Anthropic · OpenAI · DeepSeek · Gemini · Ollama — swap at runtime |
| 📋 **Workflow State Machine** | Plan → steps → execution → completion. Real-time progress bar + next-step hints |
| 🔌 **MCP Integration** | Connect any MCP server → tools auto-register. stdio/SSE/HTTP/WS transports |
| 🧩 **Sub-agent System** | `agents/*.md` definitions → `subagent` tool. Isolated context, sync/background modes |
| 🖥️ **Dual Interface** | Desktop GUI (customtkinter) + CLI with Claude Code-style transparent output |
| 🛡️ **Type-safe Tools** | 40+ tools with auto type coercion for all LLM-provided parameters |
| 🎨 **Diff Rendering** | File edits displayed as unified diff with green/red/purple syntax coloring |
| 🧪 **211+ Tests** | Comprehensive test suite covering tools, session, context, providers, and more |

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/aliquanhou/agicode.git
cd agicode
pip install -r requirements.txt
```

### Configure

```bash
# Set your API key (choose one provider)
export ANTHROPIC_API_KEY=sk-ant-your-key
# or: export OPENAI_API_KEY=sk-...
# or: export DEEPSEEK_API_KEY=sk-...
```

### Run

```bash
# GUI (recommended — full transparency experience)
python launch_gui.py

# CLI
python -m agent --cli

# Single command + JSON events (for pipe to external UI)
python -m agent --run "analyze this project" --transcript
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [📖 Quick Start Guide](docs/quickstart.md) | Install, configure, first task in 5 minutes |
| [🏗️ Architecture](docs/architecture.md) | Core loop, event bus, modules, data flow |
| [🔧 Tools Reference](docs/tools.md) | All 40+ tools with parameters and examples |
| [🤖 LLM Providers](docs/providers.md) | Setup guide for all 5 providers |
| [🧩 Sub-agent System](docs/subagents.md) | Isolated agents, definitions, background mode |
| [🔌 MCP Integration](docs/mcp.md) | Connect any MCP server, auto-register tools |
| [🖥️ GUI Guide](docs/gui.md) | Desktop app features, shortcuts, dialogs |
| [🔮 Transparency System](docs/transparency.md) | Event bus, transcript protocol, workflow state machine |
| [🛠️ Development Guide](docs/development.md) | Create tools, contribute, testing |
| [🔒 Security Guide](docs/security.md) | API key safety, permissions, best practices |

---

## 🎯 Glass-box Transparency

When you send a command, AgiCode shows **everything** in real time:

```
▶ 帮我修复这个bug

  📋 计划执行 3 个步骤
  [1/3] 📖 read  src/main.py            ← What it's doing
    ✅ 步骤 "定位错误" 完成 (1/3)
    → 下一步: 修复代码                     ← Next step

  [2/3] ✏️ edit  src/main.py  (改 8 行)
    ── 变更对比 ──                          ← Unified diff with color
    --- a/src/main.py
    +++ b/src/main.py
    @@ -42,7 +42,7 @@
  -      result = old_function(input)
  +      result = new_function(input)

    ✅ 步骤 "修复代码" 完成 (2/3)
    → 下一步: 验证修复

  📊 进度: 2/3  ▶ 当前: 修复代码  ⏭ 下一步: 验证修复
  🧠 思考 2.3s

  ✅ 所有步骤完成 (3/3) — 任务结束
```

---

## 🧰 Tool Categories

| Category | Tools | Count |
|----------|-------|-------|
| 📁 File | read, write, edit, replace, glob, grep, move, copy, delete, mkdir, download, revert | 12 |
| 💻 Shell | bash, background | 2 |
| 🌐 Web | web, web_search, browser | 3 |
| 🖥️ System | process, service, registry, gui, monitor | 5 |
| 🔬 Analysis | ast, dep_graph, call_chain, trace_error | 4 |
| 🧠 Sub-agent | subagent | 1 |
| 🔌 MCP | mcp | 1 |
| 📋 Planning | plan, task, project_memory | 3 |
| 🧠 Memory | remember | 1 |
| ⚙️ Automation | schedule, watch, websocket | 3 |
| 🧪 Testing | test, dep | 2 |
| 💬 Utility | ask_user, hash_file | 2 |

**Total: 40+ tools**

---

## 🤝 Community

- **GitHub Issues**: Bug reports, feature requests
- **Pull Requests**: Contributions welcome — see [Development Guide](docs/development.md)
- **License**: Apache 2.0 — free for personal and commercial use

### Contributing

1. Fork the repository
2. Create a feature branch
3. Write code and tests
4. Submit a Pull Request

---

## 📄 License

Apache 2.0 — See [LICENSE](LICENSE) for full text.

---

<p align="center">
  <sub>AgiCode — Built for transparency, freedom, and real work.</sub>
</p>

| Feature | Description |
|---------|-------------|
| 🔮 **Glass-box Transparency** | Every agent step → structured events (transcript bus). Users see what's happening NOW |
| 📋 **Workflow State Machine** | Plan → steps → execution → completion. Real-time progress bar + next-step hints |
| 🚫 **Zero Dead-loop** | No hard caps, no blocking detection. `while True` loop — model decides when to stop |
| 🧠 **Sub-agent System** | `agents/*.md` definitions → `subagent` tool. Isolated context, sync/background modes |
| 🔌 **MCP Integration** | Connect any MCP server → tools auto-register. stdio/SSE/HTTP/WS transports |
| 🖥️ **Claude Code-style UI** | Tool timing, step summaries, syntax-highlighted code, workflow bar, one-click log export |
| 🔧 **5 LLM Providers** | Anthropic · OpenAI · DeepSeek · Gemini · Ollama — swap at runtime |
| 🛡️ **Type-safe Tools** | Auto type coercion for all LLM-provided parameters |
| 🧪 **40+ Tools** | File, system, browser, web, analysis, planning, sub-agent, MCP, automation |
| 📤 **--transcript Mode** | JSON event stream to stdout — pipe to any external UI |

---

## Architecture / 架构

```
calw-v2.2/
├── launch_gui.py                # GUI entry point
├── main.py                      # CLI entry point
├── config.json                  # API keys + MCP server config
│
├── agent/                       # ★ Core agent package
│   │
│   │  ── v2.2 新增 ──
│   ├── transcript.py            #   Event bus — every step → structured events
│   ├── workflow.py              #   Workflow state machine — plan→steps→progress
│   ├── agent_loader.py          #   agents/*.md → Agent type registry
│   ├── tools_agent.py           #   subagent tool — isolated context execution
│   ├── mcp/client.py            #   MCP stdio client (JSON-RPC 2.0)
│   ├── tools_mcp.py             #   MCP tool — connect/discover auto-register
│   ├── agents/                  #   Agent definitions (YAML frontmatter + prompt)
│   │   ├── code-architect.md
│   │   └── code-reviewer.md
│   │
│   │  ── 核心循环 ──
│   ├── core.py                  #   Agent main loop (while True, transparent)
│   ├── providers.py             #   LLM abstraction (5 providers)
│   ├── prompt.py                #   System prompt builder
│   ├── session.py               #   Thread-safe session state (JSONL persistence)
│   ├── context.py               #   4-stage context compression
│   │
│   │  ── 工具层 ──
│   ├── tools.py                 #   Tool registry + type-safe dispatch
│   ├── tools_file.py            #   read/write/edit/replace/glob/grep/move...
│   ├── tools_shell.py           #   bash + BuildRunner
│   ├── tools_plan.py            #   plan/task/background (↔ workflow sync)
│   ├── tools_web.py             #   web/web_search/ask_user
│   ├── tools_browser.py         #   Playwright browser automation
│   ├── tools_analysis.py        #   ast/dep_graph/call_chain/trace_error
│   ├── tools_system.py          #   process/service/registry/gui/monitor
│   ├── tools_memory.py          #   Semantic memory
│   ├── tools_test.py            #   Test runner
│   ├── tools_deps.py            #   Auto install missing deps
│   ├── tools_extra.py           #   schedule/watch/websocket
│   │
│   │  ── 增强引擎 ──
│   ├── speculative.py           #   Speculative execution engine
│   ├── streaming_parser.py      #   Streaming progressive parser
│   ├── file_cache.py            #   MMAP file cache (166× speedup)
│   ├── router.py                #   Smart model router
│   ├── researcher.py            #   Deep research engine
│   ├── reviewer.py              #   Code review engine
│   ├── retry.py                 #   Exponential backoff
│   ├── app.py                   #   GUI (customtkinter, transparent)
│   └── __main__.py              #   CLI entry (+ --transcript mode)
│
├── tests/                       # 243+ tests
├── TECHNICAL_WHITEPAPER.md      # Full architecture documentation
├── CHANGELOG.md                 # Version history
└── requirements.txt             # Dependencies
```

---

## Quick Start / 快速开始

### One-liner

```bash
git clone https://github.com/aliquanhou/calw.git
cd calw
git checkout calw-v2.2
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-your-key
python launch_gui.py              # GUI mode (recommended)
```

### Configure

Edit `config.json`:
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-your-key",
  "model": "claude-sonnet-4-20250514",
  "mcp_servers": [
    {
      "name": "playwright",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-playwright"]
    }
  ]
}
```

Environment variables also work:
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key
export LLM_MODEL=claude-sonnet-4-20250514
```

### CLI Modes

```bash
# REPL (interactive console)
python -m agent --cli

# Single command
python -m agent --run "帮我查看系统状态"

# Single command + JSON event stream (for external UI)
python -m agent --run "修复这个bug" --transcript | grep @EVENT | jq .

# Single command + JSON result
python -m agent --run "查看系统信息" --json
```

### GUI Modes

```bash
# Desktop GUI (default)
python launch_gui.py
# or
python -m agent
```

---

## Glass-box Transparency / 全透明工作流

When you send a command, the GUI shows **everything** in real time:

```
▶ 帮我修复这个bug

  📋 计划执行 3 个步骤
  [1/3] 📖 read  src/main.py            ← 正在做什么
    📖 read ✅ 完成 (0.0s)
    ✅ 步骤 "定位错误" 完成 (1/3)
    → 下一步: 修复代码                     ← 下一步计划

  [2/3] ✏️ edit  src/main.py  (改 8 行)
    ✏️ edit ✅ 完成 (0.1s)
    ✅ 步骤 "修复代码" 完成 (2/3)
    → 下一步: 验证修复

  📊 进度: 2/3  ▶ 当前: 修复代码  ⏭ 下一步: 验证修复  ← 工作流进度条处于底部

  🧠 思考: 让我检查一下修复是否正确...     ← Agent 思考过程
```

**CLI `--transcript` mode** outputs every event as JSON:
```json
@EVENT {"type": "phase", "subtype": "start", "payload": {"phase_name": "plan"}}
@EVENT {"type": "plan", "subtype": "created", "payload": {"title": "修复bug", "steps": [...]}}
@EVENT {"type": "tool", "subtype": "start", "payload": {"tool_name": "read", "args": {"file_path": "src/main.py"}}}
@EVENT {"type": "tool", "subtype": "result", "payload": {"tool_name": "read", "result": "...", "duration_ms": 150}}
@EVENT {"type": "step", "subtype": "done", "payload": {"step_id": "1", "status": "done"}}
```

---

## Tools / 工具列表

| Category | Tools | Description |
|----------|-------|-------------|
| 📁 **File** | read, write, edit, replace, glob, grep, move, copy, delete, mkdir, download, revert | Full filesystem operations |
| 💻 **Shell** | bash, background | Command execution + long-running tasks |
| 🌐 **Web** | web, web_search, browser | HTTP requests, search, Playwright browser |
| 🖥️ **System** | process, service, registry, monitor, gui | Windows system control & automation |
| 🔬 **Analysis** | ast, dep_graph, call_chain, trace_error | Static code analysis |
| 🧠 **Sub-agent** | subagent | Spawn isolated agents (sync/background) |
| 🔌 **MCP** | mcp | Connect MCP servers, auto-register tools |
| 📋 **Planning** | plan, task, project_memory | Structured plans (↔ workflow sync) |
| 🧠 **Memory** | remember | Semantic memory (ChromaDB vector search) |
| ⚙️ **Automation** | schedule, watch, websocket | Cron tasks, file watcher, WebSocket client |
| 🧪 **Testing** | test, dep | Test runner + auto dependency install |
| 💬 **Utility** | ask_user, hash_file | Smart user interaction + file hashing |

---

## Sub-agent System / 子Agent系统

Define agents as simple `.md` files in `agent/agents/`:

```yaml
---
name: code-architect
description: 分析代码架构、设计方案、输出实施蓝图
model: claude-sonnet-4-20250514
tools: read, glob, grep, web_search
---

You are a senior architect. Analyze code, design solutions, output blueprints.
Do NOT modify any files — only analyze and report.
```

Then use them at runtime:
```
subagent action=run agent=code-architect prompt="分析 project/ 的模块依赖关系"
subagent action=run prompt="搜索这个错误的信息" model=claude-haiku-4-5
subagent action=agent                 # 列出可用 Agent 类型
subagent action=run prompt="审查代码" mode=background
subagent action=list                  # 查看后台子Agent
subagent action=output task_id=...    # 取后台结果
```

---

## MCP Integration / MCP 集成

Connect any MCP server — tools auto-register:

**Connect at runtime:**
```
mcp action=connect server=playwright command=npx args="[\"-y\", \"@anthropic/mcp-playwright\"]"
mcp action=list                                 # 查看已连接服务器
```

**Or auto-connect via config.json:**
```json
{
  "mcp_servers": [
    {"name": "playwright",  "command": "npx", "args": ["-y", "@anthropic/mcp-playwright"]},
    {"name": "filesystem",  "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]}
  ]
}
```

Connected MCP tools are registered as `mcp__<server>__<tool>` — usable like any built-in tool.

---

## CLI vs GUI / 两种使用方式

| Feature | CLI (`--cli`) | GUI (`launch_gui.py`) |
|---------|---------------|----------------------|
| Interface | Terminal with ANSI colors | Desktop window (customtkinter) |
| Tool transparency | Claude Code style | Same, plus code blocks |
| Real-time streaming | ✅ | ✅ |
| Workflow progress bar | ✅ (`/status`) | ✅ Bottom bar |
| Step summary + next hint | ✅ | ✅ |
| `--transcript` JSON events | ✅ | N/A |
| Keyboard shortcuts | N/A | Ctrl+Enter stop, Ctrl+R retry |
| Tool status panel | N/A | Right-side panel |
| One-click log export | N/A | 📋 Copy Log button |
| Settings | ENV + config.json | GUI dialog |

---

## v2.1 vs v2.2 Comparison / 版本对比

| Aspect | v2.1 | v2.2 |
|--------|------|------|
| **Transparency** | Basic terminal output | Event bus + workflow state machine + GUI progress bar |
| **Loop control** | `max_tool_rounds: 50` | `while True` — model decides |
| **Dead-loop detection** | Hard blocking (4 calls = break) | None — zero interference |
| **Sub-agent system** | ❌ | `subagent` tool + `agents/*.md` definitions |
| **MCP integration** | ❌ | stdio client + auto-register tools |
| **CLI --transcript** | ❌ | JSON event stream to stdout |
| **GUI rendering** | Basic | Tool timing, code blocks, step summary, next hint |
| **Plan sync** | plan writes JSON file | plan ↔ workflow state machine ↔ GUI |
| **One-click log** | ❌ | 📋 Copy Log button |
| **Agent definitions** | ❌ | YAML frontmatter + Markdown prompt |
| **Config MCP auto-connect** | ❌ | `mcp_servers` in config.json |

---

## Testing / 测试

```bash
pytest                            # Full suite
python -m pytest tests/ -v        # Verbose
python -m pytest tests/test_session.py -v
```

---

## Learn More / 了解更多

- **[Technical Whitepaper](TECHNICAL_WHITEPAPER.md)** — Full architecture, benchmarks, contribution guide
- **[Changelog](CHANGELOG.md)** — Version history v1.0 → v2.2
- **[GitHub PR #1](https://github.com/aliquanhou/calw/pull/1)** — v2.2 diff (18 files, +2039/-309)

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*AgiCode — autonomous AI engineering agent. Built for transparency, freedom, and real work.*
