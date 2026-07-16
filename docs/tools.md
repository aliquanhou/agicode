# Tools Reference

> **Complete reference for all 40+ built-in tools** — parameters, examples, and usage notes.

---

## Tool Categories

| Category | Icon | Tools |
|----------|------|-------|
| File | 📁 | read, write, edit, replace, glob, grep, move, copy, delete, mkdir, download, revert |
| Shell | 💻 | bash, background |
| Web | 🌐 | web, web_search, browser |
| System | 🖥️ | process, service, registry, gui, monitor |
| Analysis | 🔬 | ast, dep_graph, call_chain, trace_error |
| Sub-agent | 🧠 | subagent |
| MCP | 🔌 | mcp |
| Planning | 📋 | plan, task, project_memory |
| Memory | 🧠 | remember |
| Automation | ⚙️ | schedule, watch, websocket |
| Testing | 🧪 | test, dep |
| Utility | 💬 | ask_user, hash_file |

---

## 📁 File Operations

### `read` — Read file content

```
read(file_path="/path/to/file")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | Path to the file |

Returns: File content as string. Uses MMAP cache for 166× speedup.

### `write` — Write file content

```
write(file_path="/path/to/file", content="file content here")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | Path to write |
| `content` | string | ✅ | Content to write |

Returns: Success message with byte count. Automatically generates Unified Diff for GUI rendering.

### `edit` — Edit file (string replacement)

```
edit(file_path="/path/to/file", old_string="original text", new_string="replacement text")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | Path to edit |
| `old_string` | string | ✅ | Text to replace (must match exactly) |
| `new_string` | string | ✅ | Replacement text |

Returns: Success/error message with Unified Diff. Cross-platform `\r\n`/`\n` handling.

### `replace` — SEARCH/REPLACE with fuzzy matching

```
replace(file_path="/path/to/file", search="text to find", replace_text="new text", partial=false)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | Path to edit |
| `search` | string | ✅ | Text to search for |
| `replace_text` | string | ✅ | Replacement text |
| `partial` | boolean | — | Enable fuzzy matching |

### `glob` — Search file paths

```
glob(pattern="**/*.py")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pattern` | string | ✅ | Glob pattern (e.g., `**/*.py`, `src/**/*.ts`) |

Returns: Newline-separated matching paths (max 1000 results).

### `grep` — Search file content

```
grep(pattern="def _handle_", path="/project/src", glob_pattern="*.py", output_mode="content")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pattern` | string | ✅ | Regex pattern |
| `path` | string | — | Search directory (default: cwd) |
| `glob_pattern` | string | — | File name filter |
| `output_mode` | string | — | `content` or `files_with_matches` |

### `move` — Move/rename files

```
move(source="/path/old", destination="/path/new")
```

### `copy` — Copy files/directories

```
copy(source="/path/source", destination="/path/dest", recursive=false)
```

### `delete` — Delete files/directories

```
delete(path="/path/to/target", recursive=false)
```

### `mkdir` — Create directory

```
mkdir(path="/path/to/dir", parents=false)
```

### `download` — Download from URL

```
download(url="https://example.com/file.zip", destination="/path/save")
```

### `revert` — Revert file changes

```
revert(file_path="/path/to/file")
```

> ⚠️ Requires backup system (WIP in v2.2).

---

## 💻 Shell & Command Execution

### `bash` — Execute shell command

```
bash(command="python -m pytest tests/ -v", timeout=120)
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | string | ✅ | Command to execute |
| `timeout` | integer | — | Timeout in seconds (default: 120, auto-extends to 600 for builds) |

**Features:**
- Auto-detects build commands (`npm install`, `pip install`, etc.) and extends timeout
- Self-healing: cleans orphan processes before build commands
- Output streamed in real-time to GUI
- Smart truncation: preserves head + tail of long outputs
- Build pattern matching: auto-detects known errors and suggests fixes

### `background` — Background task management

```
background(action="start", command="npm run build")
background(action="list")
background(action="output", task_id="abc12345")
background(action="stop", task_id="abc12345")
background(action="wait", task_id="abc12345", pattern="ready")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | ✅ | `start`, `list`, `output`, `stop`, `stop_all`, `wait` |
| `command` | string | for `start` | Command to run in background |
| `task_id` | string | for `output/stop/wait` | Task identifier |
| `pattern` | string | — | Regex to wait for |
| `timeout` | integer | — | Wait timeout |

---

## 🌐 Web & Network

### `web` — HTTP requests

```
web(url="https://api.example.com/data", method="GET", data="", headers='{"Authorization": "Bearer xxx"}')
```

### `web_search` — Web search (DuckDuckGo)

```
web_search(query="latest AI news", max_results=5)
```

### `browser` — Browser automation (Playwright)

```
browser(action="open", url="https://example.com")
browser(action="click", selector="#button")
browser(action="type", selector="#input", text="hello")
browser(action="read", selector=".content")
browser(action="screenshot")
browser(action="diagnose", url="https://example.com")
browser(action="execute_js", script="document.title")
browser(action="close")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | ✅ | `open`, `navigate`, `click`, `type`, `read`, `screenshot`, `diagnose`, `execute_js`, `close` |
| `url` | string | — | Target URL |
| `selector` | string | — | CSS selector |
| `text` | string | — | Text to input |
| `script` | string | — | JavaScript to execute |

> **Fallback**: If Playwright is not installed, automatically degrades to HTTP fetching.

---

## 🖥️ System

### `process` — Process management

```
process(action="list")
process(action="top", sort_by="cpu")
process(action="kill", pid=1234)
process(action="launch", name="notepad.exe")
process(action="tree")
process(action="wait_exit", name="node.exe")
```

### `service` — Windows service control (Windows only)

```
service(action="list")
service(action="start", name="Spooler")
service(action="stop", name="Spooler")
service(action="restart", name="Spooler")
service(action="set_startup", name="Spooler", start_type="auto")
```

### `registry` — Windows registry operations (Windows only)

```
registry(action="read", key="HKLM:\\Software\\...")
registry(action="write", key="...", name="ValueName", value="data")
registry(action="delete", key="...", name="ValueName")
registry(action="list_keys", key="...")
```

### `gui` — GUI automation (pyautogui)

```
gui(action="click", x=100, y=200)
gui(action="type", text="hello world")
gui(action="screenshot")
gui(action="keypress", key="enter")
gui(action="locate", query="button.png")
gui(action="get_window")
```

### `monitor` — System monitoring

```
monitor(action="resources")        # CPU + memory + disk overview
monitor(action="cpu")
monitor(action="memory")
monitor(action="disk")
monitor(action="network")
monitor(action="uptime")
monitor(action="process_count")
```

---

## 🔬 Code Analysis

### `ast` — AST analysis

```
ast(file_path="/path/to/file.py")
```

Returns: Structured Python AST with classes, functions, imports, and line ranges.

### `dep_graph` — Dependency graph

```
dep_graph(path="/project/src")
```

Returns: Module dependency graph with cycle detection.

### `call_chain` — Call chain tracing

```
call_chain(function_name="handle_tool_call", direction="callers", depth=3)
```

### `trace_error` — Error trace analysis

```
trace_error(error_message="TypeError: ...", file_path="/path/to/file.py", depth=5)
```

---

## 🧠 Sub-agent

### `subagent` — Spawn isolated sub-agent

```
subagent(action="run", agent="code-architect", prompt="分析这个项目的架构")
subagent(action="run", prompt="搜索文件", model="claude-haiku-4-5", mode="background")
subagent(action="agent")                    # List available agent types
subagent(action="list")                     # List background agents
subagent(action="output", task_id="sub-001") # Get background result
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | ✅ | `run`, `agent`, `list`, `output`, `stop`, `wait` |
| `agent` | string | — | Agent type (from `agents/*.md`) |
| `prompt` | string | for `run` | Task prompt |
| `model` | string | — | Override model |
| `mode` | string | — | `sync`, `background`, `plan` |

---

## 🔌 MCP Integration

### `mcp` — MCP server management

```
mcp(action="list")
mcp(action="connect", server="playwright", command="npx", args='["-y", "@anthropic/mcp-playwright"]')
mcp(action="disconnect", server="playwright")
mcp(action="call", server="playwright", tool_name="screenshot", url="https://example.com")
```

Connected MCP tools are automatically registered as `mcp__{server}__{tool}`.

---

## 📋 Planning

### `plan` — Structured plan management

```
plan(action="create", title="重构代码", steps='[{"step": "分析"}, {"step": "实现", "depends_on": [0]}]')
plan(action="update", plan_id="plan-1", step_index=0, step_status="completed")
plan(action="list")
plan(action="show", plan_id="plan-1")
```

### `task` — Task status marker

```
task(status="done", message="重构完成")
task(status="fail", message="测试失败")
task(status="start", message="开始实现")
```

### `project_memory` — Project-level persistent memory

```
project_memory(action="read")
project_memory(action="write", content="# Project Notes\n...")
project_memory(action="append", content="New note")
```

---

## 🧠 Memory

### `remember` — Semantic memory (ChromaDB)

```
remember(action="search", query="上次的bug修复方案")
remember(action="store", content="修复了line 42的off-by-one错误", mem_type="fix")
remember(action="stats")
remember(action="context")
```

---

## ⚙️ Automation

### `schedule` — Cron task scheduling

```
schedule(action="add", name="定期清理", cron="0 9 * * *", command="Write-Host 'Cleanup'")
schedule(action="list")
schedule(action="remove", task_id="abc123")
schedule(action="events")
```

### `watch` — File/process monitoring

```
watch(action="add", name="监控日志", kind="log", path="C:\\logs\\app.log", pattern="ERROR")
watch(action="list")
watch(action="remove", watch_id="abc123")
watch(action="events", watch_id="abc123")
```

### `websocket` — WebSocket client

```
websocket(action="connect", url="wss://echo.example.com")
websocket(action="send", url="wss://echo.example.com", message="Hello")
websocket(action="ping", url="wss://echo.example.com")
```

---

## 🧪 Testing & Dependencies

### `test` — Test runner

```
test(action="discover")
test(action="run", path="tests/", test_name="test_login", timeout=300)
```

### `dep` — Auto install dependencies

```
dep(action="check", text="import pandas")
dep(action="install", module_name="pandas")
```

---

## 💬 Utility

### `ask_user` — Ask user for input

```
ask_user(question="选择部署环境", options='["开发", "测试", "生产"]', analysis="各环境对比...", recommended="测试")
```

### `hash_file` — File hashing

```
hash_file(file_path="/path/to/file", algorithm="sha256")
```

---

## Type Safety

All tools automatically coerce LLM-provided parameters based on function type annotations:

```python
def _handle_example(count: int, name: str, enabled: bool):
    # LLM sends: {"count": "42", "name": "test", "enabled": "true"}
    # AgiCode coerces: count=int(42), enabled=bool(True)
    ...
```

---

## Tool Registration

Tools are registered via `agent/tools.py`:

```python
from agent.tools import register_tool, unregister_tool, get_all_tools, execute_tool

# Register a custom tool
register_tool(
    name="my_tool",
    handler=my_function,
    description="Description for LLM",
    parameters={...},  # JSON Schema
)
```

---

*[Back to docs index](index.md)*
