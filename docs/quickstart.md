# Quick Start Guide

> **Get AgiCode running in 5 minutes** — from installation to your first autonomous task.

---

## 1. Installation

### Prerequisites

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))
- **An API key** from at least one LLM provider

### Clone & Install

```bash
git clone https://github.com/aliquanhou/agicode.git
cd agicode
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `anthropic` | >=0.30.0 | Claude API |
| `openai` | >=1.0.0 | OpenAI / DeepSeek / Ollama API |
| `customtkinter` | >=5.0.0 | GUI framework |
| `chromadb` | >=0.4.0 | Semantic memory |
| `websocket-client` | >=1.6.0 | WebSocket tool |
| `playwright` | >=1.40.0 | Browser automation |
| `pyautogui` | >=0.9.0 | GUI automation |
| `requests` | — | Web search |

> **Optional**: For Playwright browser control, also run `playwright install chromium`

---

## 2. Configuration

### Method A: Edit config.json

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-your-key-here",
  "model": "claude-sonnet-4-20250514",
  "base_url": "",
  "mcp_servers": [
    {
      "name": "playwright",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-playwright"]
    }
  ]
}
```

### Method B: Environment Variables

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
$env:LLM_MODEL = "claude-sonnet-4-20250514"

# Linux / macOS / Git Bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
export LLM_MODEL=claude-sonnet-4-20250514
```

### Supported Providers

Set the relevant environment variable for your provider:

| Provider | Environment Variable | Default Model |
|----------|---------------------|---------------|
| Anthropic Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| Gemini | `GOOGLE_API_KEY` | `gemini-pro` |
| Ollama | (local) | `ollama/llama3` |

---

## 3. Run

### GUI Mode (Recommended)

```bash
python launch_gui.py
```

This opens a desktop window with:
- Chat interface with syntax highlighting
- Real-time tool execution panel
- Workflow progress bar
- Settings dialog for API configuration

### CLI REPL Mode

```bash
python -m agent --cli
```

```
============================================================
  AgiCode - 透明自主编程
  命令: /exit 退出  /status 查看工作流
============================================================

▶ 你好，请帮我查看系统状态

  📖 read  /etc/os-release  (如果存在)
    ✔ done
  💻 bash  systeminfo
    ✔ done (42 lines)
```

### Single Command Mode

```bash
python -m agent --run "查看系统信息"
```

### JSON Transcript Mode (for external UI)

```bash
python -m agent --run "修复这个bug" --transcript
```

---

## 4. Your First Task

Once AgiCode is running, try these tasks to see it in action:

### File Operations

```
帮我创建一个 hello.py 文件，内容是一个简单的 Web 服务器
```

### Code Analysis

```
分析当前项目的模块依赖关系
```

### Web Search

```
搜索最新的 Python 3.12 新特性
```

### System Monitoring

```
查看系统 CPU 和内存使用情况
```

### Multi-step Plan

```
帮我重构当前项目的文件结构：
1. 先分析现有结构
2. 提出改进方案
3. 执行重构
```

---

## 5. Using the Sub-agent System

AgiCode can spawn isolated sub-agents for specialized tasks:

### Built-in Agent Types

| Agent | Description |
|-------|-------------|
| `code-architect` | Analyze architecture, design solutions, output blueprints |
| `code-reviewer` | Multi-dimensional code review with structured output |

### Example

```
subagent action=run agent=code-architect prompt="分析 agent/ 目录的模块依赖关系"
```

---

## 6. Connecting MCP Servers

### Auto-connect via config.json

```json
{
  "mcp_servers": [
    {"name": "playwright", "command": "npx", "args": ["-y", "@anthropic/mcp-playwright"]},
    {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]}
  ]
}
```

### Manual Connect at Runtime

```
mcp action=connect server=playwright command=npx args="[\"-y\", \"@anthropic/mcp-playwright\"]"
mcp action=list
```

---

## 7. CLI Command Reference

```bash
# Interactive REPL
python -m agent --cli

# Single command
python -m agent --run "your task"

# Single command + JSON events (for external UI)
python -m agent --run "task" --transcript

# Single command + JSON result output
python -m agent --run "task" --json

# Launch GUI
python launch_gui.py
# or
python -m agent
```

---

## 8. Keyboard Shortcuts (GUI)

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Ctrl+Enter` | Stop agent |
| `Ctrl+R` | Retry last message |
| `Ctrl+I` | Show context details |
| `Ctrl+Shift+S` | Take screenshot |

---

## 9. Configuration Reference

### config.json

```json
{
  "provider": "anthropic|openai|deepseek|gemini|ollama",
  "api_key": "your-api-key",
  "model": "model-name",
  "base_url": "optional-custom-base-url",
  "mcp_servers": [
    {"name": "...", "command": "...", "args": [...]}
  ]
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `GOOGLE_API_KEY` | Google Gemini API key |
| `LLM_MODEL` | Default model name |
| `AGICODE_MAX_TOKENS` | Max tokens per response (default: 8192) |
| `AGICODE_MAX_ROUNDS` | Max tool call rounds (default: 50) |
| `AGICODE_DATA_DIR` | Data storage directory |

---

*[Back to docs index](index.md)*
