# Sub-agent System

> **Isolated, specialized AI agents** — spawn sub-agents with custom prompts, models, and tool access.

---

## Overview

AgiCode's sub-agent system allows you to spawn **isolated agent instances** with their own context, configuration, and tool access. This enables:

- **Specialized agents**: Code architect, reviewer, researcher — each with a focused system prompt
- **Parallel execution**: Run multiple agents concurrently
- **Isolation**: Each sub-agent has its own conversation context
- **Background tasks**: Long-running analysis without blocking the main agent

---

## Agent Definitions

Agents are defined as Markdown files with YAML frontmatter in `agent/agents/`:

```markdown
---
name: code-architect
description: 分析代码架构、设计方案、输出实施蓝图
model: claude-sonnet-4-20250514
tools: read, glob, grep, web_search
color: green
---

You are a senior software architect with 20 years of experience.
Analyze code structure, design solutions, and output implementation blueprints.

## Your Role
1. Understand the codebase structure and dependencies
2. Identify architectural patterns and anti-patterns
3. Design clean, maintainable solutions
4. Output detailed implementation plans

## Constraints
- Do NOT modify any files — only analyze and report
- Always provide rationale for your recommendations
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Unique agent identifier |
| `description` | string | ✅ | One-line description shown in listings |
| `model` | string | — | Model override (inherits main agent's model if omitted) |
| `tools` | comma-separated | — | Tool whitelist (all tools available if omitted) |
| `color` | string | — | Display color (cyan, green, yellow, etc.) |

---

## Built-in Agents

### `code-architect`

**Purpose**: Analyze code architecture, design solutions, output implementation blueprints.

**Tools**: `read`, `glob`, `grep`, `web_search`

**Use cases**:
- "分析这个项目的模块依赖关系"
- "设计一个重构方案"
- "评估代码质量并提出改进建议"

### `code-reviewer`

**Purpose**: Multi-dimensional code review with structured output.

**Tools**: `read`, `glob`, `grep`

**Use cases**:
- "审查这个文件的代码质量"
- "检查这段代码的安全性"
- "分析性能瓶颈"

---

## Using Sub-agents

### Command Reference

```
subagent action=run agent=code-architect prompt="分析项目架构"
subagent action=run prompt="快速搜索"                            # 通用Agent
subagent action=run agent=code-reviewer prompt="审查代码" mode=background
subagent action=agent                                            # 列出可用Agent
subagent action=list                                              # 查看后台Agent
subagent action=output task_id=sub-001                            # 取结果
subagent action=stop task_id=sub-001                              # 终止后台任务
subagent action=wait task_id=sub-001                              # 等待完成
```

### Parameter Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | ✅ | `run`, `agent`, `list`, `output`, `stop`, `wait` |
| `agent` | string | — | Agent type name (from `agents/*.md`); empty = general-purpose |
| `prompt` | string | for `run` | Task instruction for the sub-agent |
| `model` | string | — | Override model name |
| `mode` | string | — | `sync` (default), `background`, `plan` |
| `task_id` | string | for `output/stop/wait` | Background task identifier |

---

## How It Works

### Synchronous Mode

```
Main Agent                               Sub-agent
    │                                         │
    ├── subagent(action="run", prompt="...") ─┤
    │                                         ├── Creates new Agent instance
    │                                         ├── Isolated Transcript
    │                                         ├── Independent conversation context
    │                                         ├── Executes task
    │                                         └── Returns result
    │◄────────────────────────────────────────┤
    │                                         │
```

### Background Mode

```
Main Agent                               Sub-agent (background thread)
    │                                         │
    ├── subagent(mode="background") ──────────┤
    │    Returns task_id immediately           ├── Runs in separate thread
    │                                         ├── Independent Agent instance
    │    Main agent continues working          ├── ...
    │                                         └── Result stored in registry
    │                                         │
    ├── subagent(action="output", task_id=) ──┤
    │◄────────────────────────────────────────┤
    │                                         │
```

### Implementation

The sub-agent is created in `tools_agent.py`:

```python
def _run_sub_agent(prompt: str, model: str = "") -> str:
    """Execute sub-agent in isolated context."""
    # Inherit parent configuration
    parent_state = get_state()
    parent_config = getattr(parent_state, '_config', None) or {}
    config = dict(parent_config)
    if model:
        config["model"] = model

    # Create independent transcript
    transcript = Transcript(agent_id=f"sub-{time.time():.0f}")

    # Create new agent instance
    sub_agent = Agent(config=config, transcript=transcript)
    result = sub_agent.run(prompt)
    sub_agent.close()
    return result
```

---

## Creating Custom Agents

Create a new `.md` file in `agent/agents/`:

```markdown
---
name: security-auditor
description: Security code audit specialist
model: claude-sonnet-4-20250514
tools: read, glob, grep
---

You are a security expert. Analyze code for:
- SQL injection vulnerabilities
- XSS vulnerabilities
- Insecure authentication
- Hardcoded credentials
- Unsafe deserialization

For each finding, include:
1. Severity (critical/major/minor)
2. Location (file + line)
3. Description of the vulnerability
4. Fix recommendation
```

Then use it immediately:

```
subagent action=run agent=security-auditor prompt="审计 login.py 的安全性"
```

---

## Use Cases

### Parallel Code Review

```
subagent action=run agent=code-reviewer prompt="审查 auth.py" mode=background
subagent action=run agent=code-reviewer prompt="审查 api.py" mode=background
subagent action=run agent=code-reviewer prompt="审查 models.py" mode=background

# ... later ...
subagent action=list
subagent action=output task_id=sub-001
```

### Architecture Analysis

```
subagent action=run agent=code-architect prompt="分析项目目录结构，绘制依赖关系图"
```

### Research with Cheaper Model

```
subagent action=run prompt="搜索Python 3.13新特性" model=claude-haiku-4-5
```

### Background Investigation

```
subagent action=run prompt="调查这个错误信息的原因" mode=background
```

---

*[Back to docs index](index.md)*
