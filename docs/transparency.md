# Glass-box Transparency System

> **The core innovation of AgiCode** — every agent action is a structured event, visible in real-time.

---

## What Is Glass-box Transparency?

Traditional AI agents are **black boxes**: you give them a task, they return a result, and you have no idea what happened in between. If something goes wrong, you can't see why.

AgiCode is a **glass box**: every single step — thinking, tool calls, results, plan progress — is broadcast as a structured event in real time. You see exactly what the agent is doing, right now.

```
▶ 帮我修复这个bug

  📋 计划执行 3 个步骤
  [1/3] 📖 read  src/main.py            ← 正在做什么
    ✅ 步骤 "定位错误" 完成 (1/3)
    → 下一步: 修复代码                     ← 下一步计划

  [2/3] ✏️ edit  src/main.py  (改 8 行)
    ✅ 步骤 "修复代码" 完成 (2/3)
    → 下一步: 验证修复

  📊 进度: 2/3  ▶ 当前: 修复代码  ⏭ 下一步: 验证修复

  🧠 思考: 让我检查一下修复是否正确...     ← 思考过程
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Transcript Event Bus                     │
│  (agent/transcript.py)                                      │
│                                                             │
│  emit(type, subtype, **payload) → Event                    │
│       │                                                     │
│       ├──→ Subscribers (type-specific)                      │
│       │     on("tool", callback)                            │
│       │     on("error", callback)                           │
│       │                                                     │
│       └──→ Subscribers (wildcard)                           │
│             on("*", callback)                               │
│                                                             │
│  History: last 10,000 events kept for querying              │
└─────────────────────────────────────────────────────────────┘
         │            │              │              │
         ▼            ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐
│ CLI      │ │ GUI      │ │ --transcript │ │ External     │
│ main.py  │ │ app.py   │ │ (JSON stream)│ │ Integrations │
│ ANSI     │ │ Rich     │ │ pipe to jq/  │ │ WebSocket    │
│ colors   │ │ widgets  │ │ log file     │ │ etc.         │
└──────────┘ └──────────┘ └──────────────┘ └──────────────┘
```

---

## Event Reference

### Session Events

```json
{"type": "session", "subtype": "start", "payload": {}}
{"type": "session", "subtype": "end", "payload": {"summary": {...}}}
```

### Phase Events

Track the agent's current execution phase:

```json
{"type": "phase", "subtype": "start", "payload": {"phase_name": "plan"}}
{"type": "phase", "subtype": "running", "payload": {
  "phase_name": "execute",
  "round": 3,
  "total_steps": 5,
  "completed_steps": 2
}}
{"type": "phase", "subtype": "progress", "payload": {
  "phase_name": "execute",
  "progress": 0.4,
  "workflow": {...}
}}
{"type": "phase", "subtype": "done", "payload": {
  "phase_name": "done",
  "summary": {...}
}}
```

### Step Events

Each plan step lifecycle:

```json
{"type": "step", "subtype": "start", "payload": {
  "step_id": "0", "step_name": "定位错误", "status": "running"
}}
{"type": "step", "subtype": "done", "payload": {
  "step_id": "0", "step_name": "定位错误", "status": "done",
  "result": "Found bug at line 42..."
}}
{"type": "step", "subtype": "fail", "payload": {
  "step_id": "1", "step_name": "修复代码", "status": "failed",
  "error": "File not found: src/main.py"
}}
```

### Thinking Events

Agent reasoning process (from Claude's thinking blocks or chain-of-thought):

```json
{"type": "thought", "subtype": "delta", "payload": {
  "delta": "让我分析一下这个错误..."
}}
```

### Tool Events

Full lifecycle of every tool call:

```json
{"type": "tool", "subtype": "start", "payload": {
  "tool_name": "read", "tool_id": "toolu_abc123",
  "args": {"file_path": "src/main.py"}
}}
{"type": "tool", "subtype": "result", "payload": {
  "tool_name": "read", "tool_id": "toolu_abc123",
  "result": "def main():\n    ...",
  "duration_ms": 150,
  "error_type": ""
}}
```

### Text Events

Streaming text output from the LLM:

```json
{"type": "text", "subtype": "delta", "payload": {
  "delta": "我已经分析了代码..."
}}
```

### Error Events

```json
{"type": "error", "subtype": "raised", "payload": {
  "source": "llm", "message": "API timeout after 30s"
}}
```

### Checkpoint Events

Context compression and state snapshots:

```json
{"type": "checkpoint", "subtype": "context_compressed", "payload": {
  "before": 50, "after": 32
}}
```

---

## Transcript CLI Mode

For integration with external tools and UIs:

```bash
# Run a task and pipe JSON events
python -m agent --run "analyze this bug" --transcript | grep @EVENT | jq .

# Save to file for later analysis
python -m agent --run "investigate" --transcript > session_log.jsonl

# Real-time filtering
python -m agent --run "deploy" --transcript | grep @EVENT | jq 'select(.type=="tool" and .subtype=="result")'
```

### Example Transcript Output

```
@EVENT {"type":"session","subtype":"start","payload":{},"ts":1712345678.123,"seq":1,"agent_id":"agicode"}
@EVENT {"type":"phase","subtype":"start","payload":{"phase_name":"plan"},"ts":1712345678.124,"seq":2,"agent_id":"agicode"}
@EVENT {"type":"plan","subtype":"created","payload":{"plan_id":"abc123","title":"分析bug","steps":[...]},"ts":1712345678.456,"seq":3,"agent_id":"agicode"}
@EVENT {"type":"phase","subtype":"done","payload":{"phase_name":"plan"},"ts":1712345678.457,"seq":4,"agent_id":"agicode"}
@EVENT {"type":"thought","subtype":"delta","payload":{"delta":"让我先读取文件..."},"ts":1712345678.789,"seq":5,"agent_id":"agicode"}
@EVENT {"type":"tool","subtype":"start","payload":{"tool_name":"read","tool_id":"tu_001","args":{"file_path":"src/main.py"}},"ts":1712345679.012,"seq":6,"agent_id":"agicode"}
@EVENT {"type":"tool","subtype":"result","payload":{"tool_name":"read","tool_id":"tu_001","result":"...","duration_ms":2},"ts":1712345679.015,"seq":7,"agent_id":"agicode"}
@EVENT {"type":"session","subtype":"end","payload":{"summary":{...}},"ts":1712345680.000,"seq":8,"agent_id":"agicode"}
```

---

## GUI Transparency Features

The desktop GUI (`app.py`) renders transparency events:

### Tool Status Panel

Right-side panel showing all 40+ tools with live status indicators:

- `○` Idle — gray
- `●` Running — orange (with duration)
- `✓` Done — green
- `✗` Error — red

### Workflow Progress Bar

Bottom bar showing:
- Current step name with ▶ icon
- Next step → hint
- Progress ratio (done/total)
- Status color (orange = running, green = done)

### Unified Diff Rendering

File edits display as syntax-highlighted diffs:

```
  ── 变更对比 ──
  --- a/src/main.py
  +++ b/src/main.py
  @@ -40,7 +40,7 @@
     def process_data(input):
  -      result = old_function(input)
  +      result = new_function(input)
       return result
```

Color-coded: red (-), green (+), purple (@@ hunk headers)

### Context Usage Bar

Top dashboard shows `XX% context used` with color warnings:
- Green: < 65%
- Orange: 65–85%
- Red: > 85%

### Scroll Indicator

When output scrolls past the visible area:
```
  ↓ N 条新消息  ← click to scroll to bottom
```

---

## Workflow State Machine

`agent/workflow.py` provides structured execution tracking:

### States

```
Step: pending → running → done
                   ↓         ↓
                failed    skipped
```

### Workflow Lifecycle

```
1. create_plan(title, steps)    → Plan created with step list
2. start_step(step_id)           → Mark step as running
3. complete_step(step_id, result)→ Mark step as done
4. fail_step(step_id, error)     → Mark step as failed
5. progress()                    → Returns 0.0–1.0
6. is_all_done()                 → Returns bool
```

### Plan + Task Tools

The `plan` and `task` tools automatically sync with the workflow state machine:

```python
# plan action=create creates steps in workflow
# plan action=update syncs step status to workflow
# task status=done calls workflow.complete_step()
```

---

## Querying Events

The Transcript object provides query methods:

```python
# Get recent N events
recent = transcript.recent(n=20, event_type="tool")

# Get latest event of a type
latest = transcript.latest(event_type="error")

# Generate summary
summary = transcript.summary()
# {
#   "total_events": 142,
#   "current_phase": "execute",
#   "steps_completed": 2,
#   "steps_total": 3,
#   "tool_calls": 8,
#   "errors": 0,
#   "duration_sec": 12.5
# }
```

---

## Benefits of Glass-box Design

| Aspect | Black Box (traditional) | Glass Box (AgiCode) |
|--------|------------------------|---------------------|
| Debugging | "Why did it do that?" | See every tool call, thinking step, error |
| Trust | Blind faith | Complete audit trail |
| Learning | "Magic" | Understand agent reasoning |
| Safety | Unknown actions | Real-time awareness |
| Integration | Opaque | Structured JSON events |
| User experience | Wait for result | Watch it work |

---

*[Back to docs index](index.md)*
