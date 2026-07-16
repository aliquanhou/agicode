# AgiCode Web UI v2.3 — 审核门禁 + 左中右三栏布局

> **版本:** v2.3.0 | **更新:** 2026-07-16

---

## 📐 整体架构

```
┌────────────────────────────────────────────────────────────────┐
│                         Browser                                 │
│                                                                │
│  ┌──────────┬──────────────────────┬──────────────────────┐     │
│  │  左：审核  │       中：会话       │      右：工具面板     │     │
│  │           │                      │                      │     │
│  │  ✅ 通过  │  用户消息             │  🛠 工具（11类40+）  │     │
│  │  ⚠️ 警告  │  Agent 流式回复      │  📋 工作流状态机     │     │
│  │  🔄 重试  │  📖 read file.py ✅  │  📡 事件日志（可过滤）│     │
│  │  🔧 修复  │  💻 bash ...    ✅  │  ⚙ 配置/Key管理      │     │
│  │  🚦 阻塞  │  ▼ diff 渲染        │  🧠 子Agent          │     │
│  │           │  ✏️ write ...   ✅  │  🔌 MCP 服务器管理   │     │
│  │  健康评分  │  🧠 思考块（可折叠）  │                      │     │
│  │           │                      │                      │     │
│  └────┬─────┴──────────┬───────────┴──────────┬───────────┘     │
│       │                │                      │                 │
│       ▼                ▼                      ▼                 │
│  SSE audit         SSE text/tool/step      REST / SSE          │
│  event             event                   event               │
└────────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户请求
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│  Agent Core (core.py)                                       │
│                                                            │
│  1. 建立会话上下文 → messages + system_prompt               │
│  2. while True 循环（带防死循环保护）                        │
│     ├─ 注入轮次提示到 LLM                                   │
│     ├─ 调用 LLM 流式 API                                    │
│     ├─ 解析工具调用 → 执行                                   │
│     ├─ ┌──────────────────────────────────┐                │
│     │  │ 审核引擎 (auditor.py)             │               │
│     │  │ • 10 条规则检查                   │               │
│     │  │ • BLOCK → 阻断                    │               │
│     │  │ • RETRY → 自动重试                │               │
│     │  │ • FIX   → 自动修复                │               │
│     │  │ • WARN  → 警告放行                │               │
│     │  └────────────┬─────────────────────┘               │
│     ├─ 追加结果到消息历史                                    │
│     └─ 上下文压缩（如需要）                                  │
│                                                            │
│  3. 返回最终回复 → 保存会话                                  │
└────────────────────────────────────────────────────────────┘
```

---

## 🔍 审核子代理系统（v2.3 核心）

### 设计理念

**被动观察 → 主动质量门禁**。每次工具调用后自动执行规则引擎，发现异常则自动修复/重试/阻断。

### 规则表（`agent/auditor_rules.py`）

| 规则 | 级别 | 触发条件 | 自动动作 |
|------|------|---------|---------|
| `dangerous_command` | 🚦 阻塞 | `rm -rf`/`format`/`shutdown`/`reg delete` | 直接阻断，记录到审核流水 |
| `dangerous_delete` | 🚦 阻塞 | `delete` 根目录/空路径 | 直接阻断 |
| `empty_result` | 🔄 重试 | `bash`/`web`/`grep` 返回空 | 最多重试 2 次 |
| `timeout` | 🔄 重试 | `bash` 执行 >30s | 终止后重试 1 次 |
| `network_error` | 🔄 重试 | 网络请求 timeout/refused | 最多重试 2 次 |
| `adb_not_found` | 🔄 重试 | ADB 命令报错 | 最多重试 2 次 |
| `file_not_found` | 🔧 修复 | `read` 文件不存在 | 自动创建父目录 |
| `write_failed_dir` | 🔧 修复 | `write` 目录不存在 | 自动创建目录 |
| `build_failed` | 🔧 修复 | 构建命令返回非 0 退出码 | 记录修复 |
| `grep_no_match` | ⚠️ 警告 | `grep` 无匹配 | 放行，记录警告 |
| `slow_call` | ⚠️ 警告 | 执行 >10s | 放行，记录慢调用 |
| `error_in_output` | ⚠️ 警告 | 结果含 error/exception/traceback | 放行，记录警告 |

### 审核引擎架构（`agent/auditor.py`）

```python
class Auditor:
    """单例审核引擎。"""
    
    def audit(self, tool_name, args, result, duration, error_type) -> AuditResult:
        """对一次工具调用执行全部规则检查。"""
        for rule in RULES:
            if rule.check(tool_name, args, result, duration, error_type):
                if rule.severity == BLOCK:
                    return self._block(rule, ...)    # 阻断
                if rule.severity == RETRY:
                    if retry_count < max_retries:
                        return self._retry(rule, ...) # 重试
                if rule.severity == FIX:
                    self._apply_fix(rule, args)       # 自动修复
                    return self._fix(rule, ...)
                if rule.severity == WARN:
                    return self._warn(rule, ...)      # 警告
        return self._pass(...)                        # 通过
```

### 嵌入式集成

审核引擎嵌入在 `core.py` 的工具执行循环中（第 342-357 行）：

```python
# ── 审核引擎（自动检查+修复）──
try:
    from .auditor import audit_tool_call
    audit_result = audit_tool_call(tool_name, args, result or "",
                                    elapsed_ms / 1000, error_type)
    if audit_result and audit_result.severity == "block":
        final_response += f"\n[审核] {audit_result.message}"
        _dead_loop_break = True
    if audit_result and audit_result.severity == "fix":
        result += f"\n[审核: {audit_result.message}]"
        error_type = ""
except Exception:
    pass
```

### API 端点

| 端点 | 方法 | 返回 |
|------|------|------|
| `/api/audit/stats` | GET | `{pass, warn, retry, fix, block, health}` |
| `/api/audit/report` | GET | 纯文本审核报告（可复制分享） |

---

## 🛡️ 防死循环保护（v2.2-v2.3）

### 四层防护

```
第 1 层: 硬上限 50 轮
第 2 层: 同工具名连续 12 次 → 打断
第 3 层: 输出内容哈希 20 轮无变化 → 打断
第 4 层: 轮次信号注入 LLM （"第 X/50 轮"）
```

### 代码设计

```python
# core.py 循环保护
while True:
    tool_round += 1
    
    # 第 1 层：硬上限
    if tool_round > max_rounds: break
    
    # 第 2 层：超时
    if elapsed > timeout: break
    
    # 第 3 层：同工具名检测
    recent_tool_names.append(tool_name)
    if len(set(recent_tool_names[-12:])) == 1: break
    
    # 第 4 层：内容停滞检测
    if len(set(recent_content_hashes[-20:])) == 1: break
    
    # 注入轮次提示
    round_hint = {"role": "user", "content": f"[第 {tool_round}/{max_rounds} 轮]..."}
```

### 看门狗线程

`app.py` 的 `send_text()` 方法启动看门狗守护线程：

```python
def _watchdog():
    time.sleep(600)  # 10 分钟
    if self.busy:
        self.busy = False
        # 推 SSE 通知前端
```

---

## 🎨 UI 组件详解

### 左栏 — 审核面板（`#audit`）

```
┌─────────────────────────────┐
│ 📋 审核门禁        ⚡ 健康    │
├─────────────────────────────┤
│ ┌─────┬─────┐ ┌─────┬─────┐│
│ │ ✅  │ ⚠️  │ │ 🔄  │ 🔧  ││
│ │ 45  │ 2   │ │ 1   │ 1   ││
│ │ 通过│警告  │ │重试  │修复  ││
│ ├─────┼─────┤ ├─────┼─────┤│
│ │ 🚦  │ 📊  │ │     │     ││
│ │ 0   │ 49  │ │     │     ││
│ │ 阻塞│总计  │ │     │     ││
│ └─────┴─────┘ └─────┴─────┘│
├─────────────────────────────┤
│ ✅ read   providers.py 0.1s │
│ ✅ read   router.py    0.1s │
│ ⚠️ grep   TODO 无匹配  0.0s │
│ 🔧 bash   构建失败已修复 1.5s│
│ ✅ read   config.json  0.1s │
├─────────────────────────────┤
│ [📋 复制报告] [🗑 清空]     │
└─────────────────────────────┘
```

**状态图标颜色：**
- ✅ 通过 — 绿色 (`var(--accent4)`)
- ⚠️ 警告 — 橙色 (`var(--accent5)`)
- 🔄 重试 — 蓝色 (`var(--accent7)`)
- 🔧 修复 — 紫色 (`var(--accent2)`)
- 🚦 阻塞 — 红色 (`var(--accent6)`)

**健康评分算法：**
```javascript
var ratio = (retry + fix + block) / total;
if (ratio < 0.05) → "⚡ 健康" (excellent)
if (ratio < 0.15) → "👍 良好" (good)
if (ratio < 0.30) → "⚠️ 一般" (fair)
else → "❌ 较差" (poor)
```

### 中栏 — 渲染输出

| 组件 | 说明 | CSS 类 |
|------|------|--------|
| 用户消息 | 右对齐，青色渐变背景 | `.msg-user` |
| Agent 流式文本 | 左对齐，累积渲染 (`_acc`) | `.msg-asst` |
| 工具调用行 | 紧凑一行：图标+名+路径+耗时 | `.tool-line` |
| Diff 渲染 | `+`绿 / `-`红 行，语法高亮 | `.diff-block` |
| 思考块 | 可折叠，斜体灰字 | `.think-block` |
| 步骤分隔线 | 绿色"✔ 步骤完成" | `.step-sep` |
| 系统/错误 | 居中/红色左边框 | `.msg-sys` / `.msg-err` |

### 右栏 — 工具面板（多标签）

| 标签 | 功能 | 数据来源 |
|------|------|---------|
| 🛠 工具 | 11 类 40+ 工具，实时状态指示灯 | `TOOL_CATEGORIES` 硬编码 |
| 📋 工作流 | 进度条+步骤列表+状态 | `/api/stream` SSE `phase.workflow` |
| 📡 事件 | 可过滤事件日志（最近 200 条缓存） | `S.events` array |
| ⚙ 配置 | Provider/Key/Model/BaseURL | `/api/config` |
| 🧠 子Agent | code-architect / code-reviewer | 硬编码 |
| 🔌 MCP | 服务器卡片+连接/断开表单 | `/api/mcp/servers` |

---

## 🔌 MCP 管理（v2.1+）

### 服务器连接

```bash
POST /api/mcp/connect
{"name": "filesystem", "command": "npx.cmd",
 "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]}
```

### 前端 UI

```
🔌 MCP │ 已发现 2 个服务器
─────────────────────────────
● filesystem (已连接)  [断开]
  npx.cmd ...
  🛠 read_file 🛠 write_file 🛠 list_directory ...

○ git (未连接)  [连接]
  npx.cmd ...
  0 个工具
─────────────────────────────
[+ 连接新 MCP 服务器]
```

---

## 💾 localStorage 持久化（v2.1+）

**存储内容：** 消息历史、工作流状态、事件日志、工具统计

**保存策略：**
- 关闭页面时 `beforeunload` 一次性保存
- 后台每 30s 定时保存

**恢复流程：**
```
页面加载
  → loadState() 从 localStorage 读取
    → 重建 DOM 消息列表（保留 dataset）
    → 恢复工作流、事件、统计
    → 如无数据 → 显示欢迎消息
```

**手动清空：** 点击 🗑 清空 → `localStorage.removeItem(STORAGE_KEY)`

---

## 📡 SSE 事件协议

| 事件 | 负载 | 触发时机 | 更新频率 |
|------|------|---------|---------|
| `text` | `{delta: "..."}` | LLM 流式输出文本 | 实时，每 token |
| `thought` | `{delta: "..."}` | LLM 思考过程 | 实时 |
| `tool` | `{subtype, tool_name, file_path, result, ...}` | 工具开始/结束 | 每次工具调用 |
| `session` | `{subtype: "start"|"end"}` | 会话生命周期 | 每次请求 |
| `phase` | `{phase_name, progress, workflow}` | 阶段变更 | 每轮循环 |
| `step` | `{step_id, status, step_name}` | 工作流步骤 | 每步变化 |
| `plan` | `{title, steps[]}` | 计划创建 | 执行 `plan` 工具 |
| `error` | `{message}` | 错误发生 | 出错时 |
| `audit` | `{status, tool, severity, duration, message}` | **审核结果** | **每次工具调用** |

### 重连机制

```javascript
// 指数退避重连: 1s → 2s → 4s → ... → 30s 上限
// 连接状态指示: 绿色=正常, 橙色闪烁=重连中
```

---

## 📁 文件清单

### Web UI 核心

```
agent/
├── editor/
│   ├── index.html          ← 完整 Web UI（CSS 内联）
│   └── app.js              ← 1082 行前端逻辑
├── app.py                  ← Web 应用 + SSE 桥接 + 看门狗
├── web_server.py           ← FastAPI 服务器 + REST API
├── core.py                 ← Agent 循环 + 防死锁 + 审核集成
├── auditor.py              ← 审核引擎（单例规则引擎）
├── auditor_rules.py        ← 10 条审核规则定义
├── transcript.py           ← 事件总线
├── workflow.py             ← 工作流状态机
├── tools*.py               ← 40+ 工具实现
└── mcp/                    ← MCP stdio 客户端
docs/
└── web-ui-v2.md            ← 本文档
```

### REST API 总览

| 端点 | 方法 | v2.0 | v2.1 | v2.2 | v2.3 |
|------|------|------|------|------|------|
| `/` | GET | ✅ | ✅ | ✅ | ✅ |
| `/api/stream` | GET | ✅ | ✅ | ✅ | ✅ |
| `/api/send` | POST | ✅ | ✅ | ✅ | ✅ |
| `/api/stop` | POST | ✅ | ✅ | ✅ | ✅ |
| `/api/clear` | POST | ✅ | ✅ | ✅ | ✅ |
| `/api/config` | GET/POST | ✅ | ✅ | ✅ | ✅ |
| `/api/context` | GET | ✅ | ✅ | ✅ | ✅ |
| `/api/tools` | GET | ✅ | ✅ | ✅ | ✅ |
| `/api/health` | GET | ✅ | ✅ | ✅ | ✅ |
| `/api/mcp/servers` | GET | - | ✅ | ✅ | ✅ |
| `/api/mcp/connect` | POST | - | ✅ | ✅ | ✅ |
| `/api/mcp/disconnect` | POST | - | ✅ | ✅ | ✅ |
| `/api/probe` | GET | - | - | ✅ | ✅ |
| `/api/probe/events` | GET | - | - | ✅ | ✅ |
| **`/api/audit/stats`** | GET | - | - | - | **✅** |
| **`/api/audit/report`** | GET | - | - | - | **✅** |

---

## 🚀 Quick Start

```bash
git clone https://github.com/aliquanhou/agicode.git
cd agicode
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-your-key
python -m agent
# 打开 http://127.0.0.1:<随机端口>
```

---

## 📊 版本演变

| 版本 | 标签 | 核心改进 |
|------|------|---------|
| v2.0.0 | ✅ | 零依赖 Web UI，Claude Code 风格会话 |
| v2.1.0 | ✅ | MCP 面板 + localStorage 持久化 |
| v2.2.0 | ✅ | SSE 重连 + 防死循环 + 类型注解 |
| **v2.3.0** | ✅ **最新** | **审核子代理 + 左中右三栏布局** |
