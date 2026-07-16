# GUI Guide

> **Desktop application features** — real-time workflow visualization, tool panel, and interactive controls.

---

## Overview

AgiCode's GUI (`launch_gui.py`) is built with **CustomTkinter** — a modern, dark-themed tkinter framework. It provides:

- Real-time chat interface with syntax highlighting
- Live tool execution panel
- Workflow progress tracking
- Settings management
- Context monitoring
- One-click log export

---

## Interface Layout

```
┌───────────────────────────────────────────────────────┬──────────────┐
│  Dashboard Bar                                         │              │
│  ⟐ AgiCode  [Provider] [Session] [XX% context used]   │              │
│  [Settings] [🔍 审查] [📊 研究] [⏰ 定时] [Clear]     │              │
├───────────────────────────────────────────────────────┤  🛠 工具面板  │
│  Workflow Status Bar                                   │ ─────────── │
│  ▶ 当前步骤 → 下一步                    📊 2/3         │              │
├───────────────────────────────────────────────────────┤  📂 文件系统  │
│                                                       │  ○ read      │
│  Chat Area (main)                                     │  ○ write     │
│                                                       │  ○ edit      │
│  >> 你好，请帮我查看系统状态                            │  ○ glob      │
│                                                       │  ○ grep      │
│    📖 read  /etc/os-release                           │              │
│      ✔ done (0.0s)                                   │  ⚡ 命令执行  │
│                                                       │  ○ bash      │
│    💻 bash  systeminfo                                │  ○ background│
│      ✔ done (0.5s)                                   │              │
│                                                       │  🖥️ 系统控制  │
│  🧠 思考: 让我汇总一下系统信息...                      │  ○ process   │
│                                                       │  ...         │
│  📊 进度: 2/3  ▶ 当前: 分析  ⏭ 下一步: 报告          │              │
│                                                       │  📋 日志     │
│                                                       │  10:15:03 ▶ │
│                                                       │  10:15:05 ✓ │
├───────────────────────────────────────────────────────┴──────────────┤
│  [⏹ 终止 Ctrl+Enter] [🔄 重试 Ctrl+R] [📋 复制] [📊 上下文 Ctrl+I] │
│  [输入指令，Enter 发送                                     ] [发送]  │
│  Ready — 记忆: 5轮 | 缓存: 12模块                   Status Bar      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Real-time Chat Rendering

- **Streaming text**: Tokens appear as they arrive from the LLM
- **Markdown rendering**: Code fences detected and rendered with blue syntax highlighting
- **Python syntax highlighting**: Regex-based keyword/string/number highlighting

### 2. Tool Status Panel (Right Side)

Tools are organized into categories with live status indicators:

| Indicator | State | Color |
|-----------|-------|-------|
| `○` | Idle | Gray |
| `●` | Running | Orange |
| `✓` | Done | Green |
| `✗` | Error | Red |

### 3. Workflow Progress

The workflow bar shows:
- Current step name with ▶ icon
- Next step hint with → arrow
- Completion ratio (done/total)
- Status color (orange = running, green = done)

### 4. Unified Diff Rendering

File edits display as color-coded diffs:

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

Colors: red (- deletions), green (+ additions), purple (@@ hunk headers)

### 5. Context Usage Monitor

The dashboard bar shows `XX% context used`:
- **Green**: < 65% usage
- **Orange**: 65–85% usage  
- **Red**: > 85% usage — approaching context limit

### 6. Scroll Indicator

When output scrolls past visible area, a floating indicator appears:

```
  ↓ N 条新消息   ← click to jump to latest output
```

### 7. Thinking Time Display

After each LLM call, the thinking duration is shown:

```
  🧠 思考 2.3s
```

---

## Tool Panel Categories

| Category | Icon | Tools |
|----------|------|-------|
| 📂 文件系统 | 📖 ✏️ 🔧 🔍 🔎 | read, write, edit, glob, grep |
| ⚡ 命令执行 | 💻 ⏳ | bash, background |
| 🖥️ 系统控制 | 🖥️ ⚙️ | process, service, registry, gui, monitor |
| 🧠 智能与网络 | 🧠 🌐 | think, web, web_search, browser |
| 🌍 浏览器 | 🌍 | browser |
| 🔬 代码分析 | 🌳 🕸 🔗 | ast, dep_graph, call_chain |
| 📋 工具链 | 📋 ✅ | plan, task |

---

## Quick Action Buttons

Located above the input area:

| Button | Shortcut | Description |
|--------|----------|-------------|
| ⏹ 终止 | `Ctrl+Enter` | Immediately stop current execution |
| 🔄 重试 | `Ctrl+R` | Re-send last user input |
| 📋 复制 | — | Copy all conversation to clipboard |
| 📊 上下文 | `Ctrl+I` | Show detailed context breakdown |

---

## Settings Dialog

Configure all provider settings in one dialog:

| Setting | Description |
|---------|-------------|
| LLM 提供商 | Provider selection dropdown |
| API 密钥 | API key (masked input) |
| API 地址 | Custom base URL (for OpenAI-compatible APIs) |
| 模型 | Model selection dropdown (provider-dependent) |
| 系统提示词 | Custom system prompt editor |

---

## Feature Dialogs

### 🔍 Code Review

Opens a dialog to review code changes or files:

- **Depth**: Low (quick) / Medium / High (deep)
- **审查变更**: Review working tree diff
- **审查文件**: Review a specific file
- **导出**: Save review as Markdown

### 📊 Deep Research

Multi-source research interface:

- Research question input
- Source count selector (3/5/8/10)
- Fact-check toggle
- Real-time progress bar

### ⏰ Scheduled Tasks

Cron task management:

- Name, cron expression, command
- Task list with enable/disable toggle
- Recent events log

### 👁 File Monitoring

Real-time file watching:

- Types: file / directory / log / process
- Pattern matching (regex)
- Event log display

---

## Context Detail Panel

Press `Ctrl+I` to see:

```
── 上下文明细 ──
模型限额: 200K tokens
总使用:   45.2K tokens (22.6%)
系统提示词: ~1,200 tokens
  user: 12.5K
  assistant: 28.3K
  tool: 4.4K
消息条数: 24
```

---

## Tips & Tricks

### Best Practices

1. **Configure API key first** — click ⚙️ Settings before starting
2. **Watch the context bar** — `>85%` means it's time to start a new session
3. **Use Ctrl+R** to retry when the agent makes a wrong turn
4. **Use Ctrl+Enter** to stop a runaway task
5. **Use 📋 copy** to export sessions for sharing or analysis

### Performance Notes

- The GUI uses `tkinter.Text` for chat — very large conversations (>50K chars) may slow down
- Syntax highlighting is time-bounded (150ms max) to prevent UI freezing
- The watchdog automatically resets after 300s of no output

---

*[Back to docs index](index.md)*
