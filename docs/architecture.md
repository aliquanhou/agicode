# Architecture

> **AgiCode Architecture** — How the glass-box autonomous agent works under the hood.

---

## Table of Contents

1. [Core Design Principles](#1-core-design-principles)
2. [System Overview](#2-system-overview)
3. [Agent Core Loop](#3-agent-core-loop)
4. [Event Bus (Transcript)](#4-event-bus-transcript)
5. [Workflow State Machine](#5-workflow-state-machine)
6. [LLM Provider Abstraction](#6-llm-provider-abstraction)
7. [Tool System](#7-tool-system)
8. [Context Management](#8-context-management)
9. [Session Management](#9-session-management)
10. [Data Flow Diagrams](#10-data-flow-diagrams)

---

## 1. Core Design Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Glass-box Transparency** | Every agent step → structured events. Users see what's happening NOW. |
| 2 | **Zero Dead-loop** | `while True` loop — model decides when to stop. No hard caps, no blocking detection. |
| 3 | **Plan-first Execution** | Agent must create a structured plan before acting. Steps decompose the task. |
| 4 | **LLM-agnostic** | Unified interface for 5 providers. Swap at runtime without code changes. |
| 5 | **Type-safe Tools** | Auto type coercion for all LLM-provided parameters. |
| 6 | **Self-healing** | Orphan process cleanup, retry with backoff, automatic dependency installation. |

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────────┐  │
│  │ CLI      │  │ GUI      │  │ --transcript (JSON stream)   │  │
│  │ main.py  │  │ app.py   │  │ (pipe to external UI)        │  │
│  └────┬─────┘  └────┬─────┘  └──────────────┬───────────────┘  │
│       │             │                        │                   │
└───────┼─────────────┼────────────────────────┼───────────────────┘
        │             │                        │
        ▼             ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Core (core.py)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Transcript  │  │ Workflow     │  │ Session State        │  │
│  │ Event Bus   │  │ State Machine│  │ (JSONL persistence)  │  │
│  └─────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Main Loop (while True)                      │  │
│  │  1. Stream LLM → 2. Parse tool_calls → 3. Execute       │  │
│  │  4. Push events → 5. Repeat until no tool_calls          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌────────────────┐  ┌──────────────────┐
│ Tool Registry │  │ LLM Providers │  │ Context Manager  │
│ (tools.py)    │  │ (providers.py)│  │ (context.py)     │
│               │  │                │  │                  │
│ 40+ tools     │  │ Anthropic     │  │ 4-stage          │
│ Type-safe     │  │ OpenAI        │  │ compression      │
│ Auto-register │  │ DeepSeek      │  │ Token estimation │
│ Plugin system │  │ Gemini        │  │ Integrity checks │
│ MCP bridge    │  │ Ollama        │  │                  │
└───────────────┘  └────────────────┘  └──────────────────┘
```

---

## 3. Agent Core Loop

The main loop in `core.py::Agent.run()` is the heart of AgiCode:

```
User Message
    │
    ▼
┌─────────────────────────────────┐
│ 1. Build Context               │
│    • Load recent messages       │
│    • Build system prompt        │
│    • Inject memory context      │
│    • Inject project map         │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ 2. LLM Call (streaming)        │◄────────────────────┐
│    • Stream tokens in real-time │                     │
│    • Collect text + tool_calls  │                     │
│    • Push transcript events     │                     │
└──────────────┬──────────────────┘                     │
               │                                        │
               ▼                                        │
        ┌───────────┐                                   │
        │ Any tool  │──── No ──► Return final response   │
        │  calls?   │                                     │
        └─────┬─────┘                                     │
              │ Yes                                       │
              ▼                                           │
┌─────────────────────────────────┐                       │
│ 3. Execute Tools               │                       │
│    • Parse arguments (type-safe)│                       │
│    • Execute via tool registry  │                       │
│    • Push tool result events    │                       │
│    • Append to message history  │                       │
└──────────────┬──────────────────┘                       │
               │                                          │
               ▼                                          │
┌─────────────────────────────────┐                       │
│ 4. Loop Detection / Compaction  │                       │
│    • Compact context if needed  │                       │
│    • Sync workflow progress     │────────────────────────┘
└─────────────────────────────────┘
```

**Key properties:**
- **No hard cap** on tool rounds — the model decides when the task is complete
- **Streaming-first** — every token arrives in real-time via callbacks
- **Self-healing** — LLM failures trigger exponential backoff retry
- **Transparent** — every step produces structured events

---

## 4. Event Bus (Transcript)

`agent/transcript.py` implements a typed event system that broadcasts every agent action:

### Event Types

| Event Type | Description | Subtypes |
|-----------|-------------|----------|
| `SESSION` | Conversation session lifecycle | `start`, `end` |
| `PHASE` | Execution phase transitions | `plan`, `execute`, `verify`, `done` |
| `STEP` | Workflow step lifecycle | `created`, `start`, `done`, `fail`, `skipped` |
| `THOUGHT` | Agent reasoning (thinking blocks) | `delta` |
| `TOOL` | Tool call lifecycle | `start`, `param`, `result` |
| `TEXT` | Streaming text output | `delta` |
| `LOOP` | Loop detection / dead-loop prevention | `warning`, `break` |
| `ERROR` | Error events | `raised` |
| `CHECKPOINT` | Context compression / state snapshots | `context_compressed` |
| `PLAN` | Plan lifecycle | `created`, `step_planned` |

### Event Structure

```json
{
  "type": "tool",
  "subtype": "result",
  "ts": 1712345678.123,
  "seq": 42,
  "agent_id": "agicode",
  "payload": {
    "tool_name": "read",
    "tool_id": "toolu_abc123",
    "result": "file content...",
    "duration_ms": 150,
    "error_type": ""
  }
}
```

### Subscription API

```python
transcript = Transcript(agent_id="agicode")

# Subscribe to all events
transcript.on("*", lambda e: print(e.dict()))

# Subscribe to specific types
transcript.on("tool", lambda e: print(f"Tool: {e.payload['tool_name']}"))
transcript.on("error", lambda e: print(f"Error: {e.payload['message']}"))
```

### Transcript CLI Mode

Run with `--transcript` flag for JSON event stream:

```bash
python -m agent --run "fix this bug" --transcript | grep @EVENT | jq .
```

Output:
```
@EVENT {"type": "phase", "subtype": "start", "payload": {"phase_name": "plan"}}
@EVENT {"type": "plan", "subtype": "created", "payload": {"title": "修复bug", "steps": [...]}}
@EVENT {"type": "tool", "subtype": "start", "payload": {"tool_name": "read", "args": {...}}}
@EVENT {"type": "tool", "subtype": "result", "payload": {"tool_name": "read", ...}}
@EVENT {"type": "step", "subtype": "done", "payload": {"step_id": "1", "status": "done"}}
```

---

## 5. Workflow State Machine

`agent/workflow.py` manages structured execution plans:

### Step States

```
pending ──► running ──► done
                │
                ├──► failed
                └──► skipped
```

### Workflow Lifecycle

```
Create Plan → Start Step → Execute → Complete/Fail → Next Step → All Done
```

### Key Methods

| Method | Description |
|--------|-------------|
| `create_plan(title, steps)` | Create a new plan with step dependencies |
| `get_ready_steps()` | Get steps whose dependencies are met |
| `start_step(step_id)` | Mark a step as running |
| `complete_step(step_id, result)` | Mark step as done |
| `fail_step(step_id, error)` | Mark step as failed |
| `progress()` | Returns 0.0–1.0 completion ratio |

### Plan + Task Tools

The `plan` and `task` tools synchronize with the workflow state machine automatically:

```
User: 先计划再执行
Agent: plan action=create title="修复bug" steps='[{"step": "定位错误"}, {"step": "修复代码", "depends_on": [0]}]'
  → Workflow created with 2 steps

Agent: plan action=update plan_id=plan-1 step_index=0 step_status=in_progress
  → Workflow.start_step("0")

Agent: task status=done message="找到bug在line 42"
  → Workflow.complete_step("0")
```

---

## 6. LLM Provider Abstraction

`agent/providers.py` provides a unified interface for 5 LLM providers:

### Provider Interface

```python
class LLMProvider:
    def complete(self, system, messages, tools=None, max_tokens=8192, temperature=0.0) -> dict:
        """Non-streaming completion."""
        ...

    def stream_complete(self, system, messages, tools=None,
                        max_tokens=8192, temperature=0.0,
                        on_text=None, on_tool_start=None, on_thinking=None) -> dict:
        """Streaming completion with callbacks."""
        ...
```

### Supported Providers

| Provider | Model Prefix | Key Env Var | Base URL |
|----------|-------------|-------------|----------|
| **Anthropic Claude** | `claude-*` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` |
| **OpenAI** | `gpt-*` / `openai/` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| **DeepSeek** | `deepseek-*` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` |
| **Gemini** | `gemini-*` | `GOOGLE_API_KEY` | (Google AI) |
| **Ollama** | `ollama/` | — | `http://localhost:11434/v1` |

### Model Routing

The factory `create_llm_provider(config)` auto-detects provider from model name:

```python
# Auto-detected as Anthropic
config = {"model": "claude-sonnet-4-20250514", "api_key": "sk-ant-..."}

# Auto-detected as DeepSeek
config = {"model": "deepseek-chat", "api_key": "sk-..."}

# Explicit OpenAI-format
config = {"model": "openai/gpt-4o", "api_key": "sk-..."}
```

---

## 7. Tool System

`agent/tools.py` implements a thread-safe, type-safe tool registry:

### Registration

```python
register_tool(
    name="my_tool",
    handler=my_handler_func,
    description="Does something useful",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "First parameter"},
            "param2": {"type": "integer", "description": "Second parameter"},
        },
        "required": ["param1"],
    },
)
```

### Auto-registration from Modules

Tools are auto-discovered from modules by naming convention — functions prefixed with `_handle_` are automatically registered:

```python
# agent/tools_file.py
def _handle_read(file_path: str = "") -> str:
    """Read file content."""
    ...

# Automatically registered as tool "read"
# Parameters auto-inferred from function signature
```

### Tool Categories

| Category | Tools | Description |
|----------|-------|-------------|
| 📁 File | read, write, edit, replace, glob, grep, move, copy, delete, mkdir, download, revert | Full filesystem operations |
| 💻 Shell | bash, background | Command execution + long-running tasks |
| 🌐 Web | web, web_search, browser | HTTP requests, search, Playwright browser |
| 🖥️ System | process, service, registry, monitor, gui | Windows system control & automation |
| 🔬 Analysis | ast, dep_graph, call_chain, trace_error | Static code analysis |
| 🧠 Sub-agent | subagent | Spawn isolated agents (sync/background) |
| 🔌 MCP | mcp | Connect MCP servers, auto-register tools |
| 📋 Planning | plan, task, project_memory | Structured plans (↔ workflow sync) |
| 🧠 Memory | remember | Semantic memory (ChromaDB vector search) |
| ⚙️ Automation | schedule, watch, websocket | Cron tasks, file watcher, WebSocket client |
| 🧪 Testing | test, dep | Test runner + auto dependency install |

### Type Safety

The `_coerce_params()` function automatically converts LLM-provided string parameters to the correct Python types based on the handler function's type annotations:

```python
def _handle_example(count: int, enabled: bool, rate: float):
    # LLM might send count="3", enabled="true", rate="1.5"
    # These are automatically coerced to int(3), bool(True), float(1.5)
    ...
```

---

## 8. Context Management

`agent/context.py` implements 4-stage progressive compression to stay within model context limits:

### Stage 1: Truncate Tool Results

Tool results exceeding 6000 chars are smart-truncated (head + tail preservation).

### Stage 2: Compact Old Messages

Older messages beyond the recent 8 turns are compacted:
- Content truncated to 300 chars
- Tool results replaced with `[工具结果已压缩]`
- Tool calls replaced with tool name list

### Stage 3: Drop Oldest Turns

If still over budget, oldest turns are dropped while keeping a project state snapshot.

### Stage 4: Integrity Sanitization

Ensures tool_call/tool_result pairing integrity after compression — orphan tool results are removed.

### Context Limit Reference

| Model Family | Context Limit |
|-------------|---------------|
| Claude | 200,000 tokens |
| GPT-4 / GPT-4o | 128,000 tokens |
| DeepSeek | 65,536 tokens |

---

## 9. Session Management

`agent/session.py` manages conversation lifecycle:

### SessionState

```python
state = SessionState(user_id="default")

# Messages persisted as JSONL
state.add_message("user", "Hello")
state.add_message("assistant", "Hi! How can I help?")
recent = state.get_recent_messages(max_count=50)

# Error logging
state.log_error("llm_complete", "API timeout", traceback.format_exc())

# Workflow sync (for plan/task tools)
set_session_workflow(workflow)
```

### Persistence

- Messages stored as JSONL: `data/{user_id}/messages.jsonl`
- Errors stored as JSONL: `data/{user_id}/errors.jsonl`
- Semantic memory: ChromaDB vector store

---

## 10. Data Flow Diagrams

### Tool Execution Flow

```
LLM decides to call tool
        │
        ▼
┌──────────────────┐
│ Parse arguments  │── JSON string → dict
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Type Coercion    │── string "42" → int 42
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Execute Handler  │── handler(**safe_params)
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Result → String  │── unified string return
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Push Event       │── transcript.tool("result", ...)
└──────────────────┘
```

### Streaming Text Flow

```
LLM Stream
    │
    ▼
┌──────────────────┐
│ provider         │── on_text(delta)
│ stream_complete  │── on_tool_start(name, input)
│                  │── on_thinking(delta)
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Agent._stream_llm│── transcript.text(delta=text)
│                  │── transcript.thought(delta=text)
└──────┬───────────┘
       ▼
┌──────────────────┐
│ StreamHandler    │── handler.on_text(text)
│ (UI/CLI)         │── handler.on_thinking(text)
└──────────────────┘
```

---

## Module Dependency Map

```
core.py
  ├── transcript.py    (event bus)
  ├── workflow.py      (state machine)
  ├── tools.py         (tool registry)
  │   ├── tools_*.py   (15 tool modules)
  │   ├── mcp/client.py
  │   └── tools_mcp.py
  ├── providers.py     (LLM abstraction)
  ├── session.py       (state management)
  ├── prompt.py        (prompt building)
  ├── context.py       (compression)
  ├── memory.py        (persistence)
  └── memory_v2.py     (semantic memory)
```

---

*[Back to docs index](index.md)*
