# AgiCode Web UI v2.0 — Glass-box Agent Interface

> **设计哲学:** 受 Claude Code 启发的轻量级 diff 优先会话界面，零编辑器依赖，全事件透明。

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser                           │
│  ┌──────────────────────┐  ┌──────────────────┐     │
│  │   Chat (agent/       │  │  Side Panel       │     │
│  │   editor/index.html  │  │  Tools │ WF │ Ev  │     │
│  │   + app.js)          │  │  Config │ Agents  │     │
│  │                      │  │                  │     │
│  │  • User messages     │  │  • 40+ tool grid │     │
│  │  • Tool call lines   │  │  • Workflow steps│     │
│  │  • Inline diffs      │  │  • Event log     │     │
│  │  • Thinking blocks   │  │  • Settings      │     │
│  └──────────┬───────────┘  └────────┬─────────┘     │
└─────────────┼───────────────────────┼───────────────┘
              │  SSE (Server-Sent     │
              │  Events)              │ REST API
              ▼                       ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Server (uvicorn)                 │
│  ┌────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ /api/stream │  │ /api/send │  │ /api/config    │  │
│  │ SSE events  │  │ POST msg  │  │ GET/POST       │  │
│  │ text/thought│  │ /api/stop │  │ /api/context   │  │
│  │ tool/step/  │  │ /api/clear│  │ /api/tools     │  │
│  │ session/…   │  │ /api/retry│  │ /api/health    │  │
│  └──────┬──────┘  └─────┬────┘  └────────────────┘  │
└─────────┼────────────────┼──────────────────────────┘
          │                │
          ▼                ▼
┌─────────────────────────────────────────────────────┐
│                   Agent Core                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │
│  │ core.py  │  │transcript│  │  Agent Loop      │    │
│  │  Agent   │◄─┤ Event Bus│◄─│  while True      │    │
│  │  class   │  │  .on("*")│  │  plan→tool→done  │    │
│  └──────────┘  └──────────┘  └────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 📡 Event Protocol (SSE)

The server pushes structured events via Server-Sent Events at `/api/stream`:

### Event Types

| Event | Subtypes | Payload | Purpose |
|-------|----------|---------|---------|
| `text` | — | `{delta: "..."}` | Streaming agent response text |
| `thought` | — | `{delta: "..."}` | Thinking/reasoning process |
| `tool` | `start` | `{tool_name, file_path, args_preview}` | Tool invocation |
| `tool` | `result` | `{tool_name, status, result, duration_ms}` | Tool completion |
| `session` | `start/end` | — | Session lifecycle |
| `phase` | — | `{phase_name, progress, workflow}` | Execution phase |
| `step` | — | `{step_id, status, step_name}` | Workflow step update |
| `plan` | `created` | `{title, steps[]}` | Plan creation |
| `error` | — | `{message}` | Error notification |

### Event Flow Diagram

```
User Send Message
  │
  ├─ session:start
  ├─ plan:created  (steps: [...])
  │
  ├─ phase:running
  ├─ tool:start    (tool_name: "read", file_path: "file.py")
  ├─ tool:result   (status: "done", duration_ms: 150)
  │
  ├─ step:done     (step_name: "分析代码", status: "done")
  ├─ phase:progress (progress: 0.5, workflow: {...})
  │
  ├─ text:delta    ("修复完成，以下是改动：")
  ├─ tool:start    (tool_name: "edit", ...)
  ├─ tool:result   (status: "done", ...)
  │
  ├─ phase:done    (summary: {...})
  ├─ session:end
  │
  └─ Client receives final text delta
```

---

## 🎨 UI Components

### Chat Messages

Messages are rendered as **streaming text blocks** with markdown-like formatting:

```html
<!-- User message -->
<div class="msg msg-user">
  <div class="mc">修复这个bug</div>
  <div class="mt">12:30:45</div>
</div>

<!-- Tool call (compact one-liner) -->
<div class="tool-line" data-tname="read">
  <span class="tl-icon">📖</span>
  <span class="tl-name">read</span>
  <span class="tl-target">src/main.py</span>
  <span class="tl-status tl-done">✅ <span class="tl-time">0.2s</span></span>
</div>

<!-- Assistant message (streaming, accumulated via _acc) -->
<div class="msg msg-asst">
  <div class="mc"><strong>修复完成</strong><br>...</div>
  <div class="mt">12:30:47</div>
</div>
```

**Key design decisions:**

- **No Monaco Editor** — inline diff rendering is lighter and faster
- **Streaming accumulation** — each `text` delta appends to `_acc`, full `innerHTML` re-rendered via `md()`
- **Tool-to-result pairing** — sequential matching via `data-tname` dataset + pending status lookup
- **Inline diff blocks** — Unified Diff parsed and rendered as `+` (green) / `-` (red) lines with syntax highlighting

### Diff Rendering

The diff parser converts Unified Diff into DOM elements:

```javascript
// Input: Unified Diff text
@@ -42,7 +42,7 @@
-function oldFunction() {
+function newFunction() {

// Output: DOM structure
<div class="diff-block">
  <div class="diff-hdr">📝 +1  -1  ·  python</div>
  <div class="diff-body">
    <div class="diff-hunk">@@ -42,7 +42,7 @@</div>
    <div class="diff-line diff-del">
      <span class="diff-num"></span>
      <span class="diff-sig">-</span>
      <span class="diff-code"><span style="color:#7c3aed;font-weight:600">function</span> oldFunction() {</span>
    </div>
    <div class="diff-line diff-add">
      <span class="diff-num"></span>
      <span class="diff-sig">+</span>
      <span class="diff-code"><span style="color:#7c3aed;font-weight:600">function</span> newFunction() {</span>
    </div>
  </div>
</div>
```

**Behavior:**
- Auto-collapses if >30 lines (`▶` expander)
- Scrollable body if >50 lines (max-height: 300px)
- Syntax highlighting: keywords (purple), strings (orange), comments (gray italic), numbers (green)

### Side Panel

| Tab | Content | Source |
|-----|---------|--------|
| 🛠 工具 | 11 categories × 40+ tools with live status dots | `TOOL_CATEGORIES` in app.js |
| 📋 工作流 | Progress bar + step list from workflow state machine | `/api/stream` → `phase.workflow` |
| 📡 事件 | Filterable event log with type badges | `S.events[]` buffer (max 500) |
| ⚙ 配置 | Provider/key/model/URL + save + test connection | `/api/config` |
| 🧠 子Agent | Code-architect / code-reviewer cards | `agent/agents/*.md` |

---

## 🔧 Backend Integration Points

### `agent/app.py` — `WebStreamHandler`

```python
class WebStreamHandler(StreamHandler):
    def __init__(self, web_server, transcript=None):
        # Uses callback path (on_tool_start / on_tool_result)
        # NOT transcript subscription (avoids duplicate events)

    def on_tool_start(self, name, input_data):
        # Extracts file_path/command/url from input_data
        # Pushes SSE: {type: "tool", subtype: "start", tool_name, file_path, args_preview}

    def on_tool_result(self, result):
        # Pops from FIFO queue for correct tool-name pairing
        # Pushes SSE: {type: "tool", subtype: "result", tool_name, status, result, duration_ms}
```

### `agent/core.py` — Callback Activation

```python
# Critical fix: on_tool_start was never called before v2.0
# Now called before every tool execution:
if on_tool_start:
    on_tool_start(tool_name, args)
```

### `agent/web_server.py` — REST API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve `editor/index.html` |
| `/api/stream` | GET | SSE event stream |
| `/api/send` | POST | Send user message |
| `/api/stop` | POST | Stop agent execution |
| `/api/clear` | POST | Clear session |
| `/api/config` | GET/POST | Read/write configuration |
| `/api/context` | GET | Get agent status |
| `/api/health` | GET | Health check |

---

## 🧪 Version Audit — v2.0 Changes

### Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `agent/editor/index.html` | **Rewrite** | Complete UI: canvas background, chat, side panel, workflow bar, modal |
| `agent/editor/app.js` | **Rewrite** | 719 lines: streaming text, inline diff, tool pairing, 5 side tabs, particle animation |
| `agent/editor/style.css` | Deleted | Merged into index.html as `<style>` for zero-network-deploy |
| `agent/app.py` | **Fix** | WebStreamHandler: FIFO queue for tool pairing, no transcript subscription (eliminates duplicates) |
| `agent/core.py` | **Fix** | Added `on_tool_start(tool_name, args)` callback; bridge handler `thinking`→`thought` type fix |
| `agent/web_server.py` | Minor | Static file Cache-Control headers |
| `agent/router.py` | **Fix** | Plan keywords: added "拆分", "微服务", "架构设计" (fixes test_router.py) |
| `tests/test_providers.py` | Fix | Aligned with router changes |
| `tests/test_router.py` | Fix | Test expectations updated |

### Bug Fixes

| # | Bug | Root Cause | Fix |
|---|-----|------------|-----|
| 1 | Tool names invisible in output | `on_tool_start` callback never invoked in `core.py:run()` | Added explicit callback call before tool execution |
| 2 | Text chunks not accumulating | Each SSE `text` delta replaced prior content | Added `_acc` property + full re-render |
| 3 | Duplicate events (tools + thinking time x2) | WebStreamHandler subscribed to both transcript and callbacks | Removed transcript subscription, single callback path |
| 4 | `%%IC0%%` / `%%CB0%%` visible as text | md() protected → escaped → never restored | Fixed restore before `<br>` replacement |
| 5 | `<strong>` tags shown as literal text | `esc()` applied after markdown processing | Removed `esc()` on already-safe HTML |
| 6 | Multiple same-name tools (bash) paired wrong | `querySelector` found last match, not first pending | Sequential scan: first matching name + pending status |
| 7 | Thinking events lost in CLI bridge | `_bridge_handler` checked `event.type == "thinking"` but actual type was `"thought"` | Added `"thought"` to the check |
| 8 | Server startup encoding error | `print("✅")` on Windows GBK terminal | Added `PYTHONIOENCODING=utf-8` |

---

## 📊 Performance Characteristics

| Metric | Value |
|--------|-------|
| HTML + CSS + JS size | ~45 KB uncompressed |
| External dependencies | 0 (zero CDN, zero npm) |
| Monaco Editor | Removed (was 16 MB+ CDN load) |
| SSE reconnect | Browser-native (automatic) |
| Event buffer | Max 500 events in memory |
| Diff collapse threshold | 30 lines (auto-collapse), 50 lines (max-height scroll) |

---

## 🔒 Security Considerations

- **API keys** are sent to server via POST `/api/config`; masked as `"****"` in GET responses
- **SSE endpoints** are localhost-only (127.0.0.1:random-port)
- **No external CDN** — zero third-party JS execution
- **File paths** in diff blocks are escaped via `textContent`
- **User input** is escaped via `esc()` before DOM insertion

---

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/aliquanhou/agicode.git
cd agicode
pip install -r requirements.txt

# Configure
export ANTHROPIC_API_KEY=sk-ant-your-key
# or edit config.json

# Launch Web UI
python -m agent
# Open http://127.0.0.1:<random-port>
```

---

## 📐 File Map

```
agicode/
├── agent/
│   ├── editor/
│   │   └── index.html        ← Web UI (HTML + CSS + JS, all-in-one)
│   ├── app.py                ← Web application lifecycle + SSE bridge
│   ├── core.py               ← Agent main loop (callbacks fixed)
│   ├── transcript.py         ← Event bus
│   ├── workflow.py           ← State machine
│   ├── web_server.py         ← FastAPI + SSE
│   ├── tools*.py             ← 40+ tool implementations
│   └── agents/*.md           ← Sub-agent definitions
└── docs/
    └── web-ui-v2.md          ← This document
```
