# Security Guide

> **Best practices for secure usage of AgiCode** — API key management, permission controls, and safe operation.

---

## API Key Security

### ⚠️ Critical: Protect Your API Keys

API keys grant access to paid LLM services. Treat them like passwords.

### Recommended: Environment Variables

```bash
# Windows PowerShell (session scope)
$env:ANTHROPIC_API_KEY = "sk-ant-your-key"

# Permanent (Windows)
setx ANTHROPIC_API_KEY "sk-ant-your-key"

# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

### Alternative: config.json (with .gitignore)

The `.gitignore` file excludes `config.json` from version control:

```gitignore
config.json
```

**Verify it's excluded:**

```bash
git check-ignore config.json
# Should output: config.json
```

### ❌ Never

- Commit API keys to git
- Share screenshots showing keys
- Hardcode keys in source code
- Post keys in public forums or logs

---

## Permission Model

### Tool Access

AgiCode tools execute with the user's system permissions. Tools that modify the system require attention:

| Risk Level | Tools | Description |
|-----------|-------|-------------|
| 🟢 Safe | read, glob, grep, web, web_search | Read-only operations |
| 🟡 Caution | write, edit, delete, bash | Write/modify operations |
| 🔴 High | process, service, registry, gui | System control operations |

### Security Features

1. **GUI automation** (`pyautogui`) uses `FAILSAFE=True` — move mouse to top-left corner to abort
2. **Background tasks** are isolated and monitored
3. **Orphan process cleanup** runs automatically
4. **Context compression** never exposes sensitive data in summaries

---

## Safe Usage Guidelines

### Running Untrusted Commands

AgiCode executes shell commands via the `bash` tool. Be aware:

- The agent has access to your system
- Commands run with your user privileges
- Review commands before execution (GUI shows real-time output)

### Recommended Practices

| Practice | Why |
|----------|-----|
| Use a dedicated API key | Limit blast radius if key is leaked |
| Monitor active sessions | Watch the tool panel for unexpected actions |
| Set appropriate timeouts | Prevent runaway commands |
| Review MCP server configs | Only connect trusted MCP servers |
| Regular key rotation | Rotate API keys periodically |

---

## MCP Security

When connecting MCP servers:

1. **Trust the source** — Only connect MCP servers from trusted publishers
2. **Review tool permissions** — MCP tools inherit the host process's permissions
3. **Isolate MCP processes** — MCP servers run as separate processes but share your system access

---

## Data Privacy

### Local Storage

| Data | Location | Format |
|------|----------|--------|
| Conversation history | `data/{user_id}/messages.jsonl` | JSONL |
| Error logs | `data/{user_id}/errors.jsonl` | JSONL |
| Semantic memory | `.claude/memory_v2/` | ChromaDB SQLite |
| Plans | `.claude/plans/*.json` | JSON |

### What's NOT Stored

- API keys (config.json excluded from git)
- System credentials
- Browser session data (cleared on browser close)

### Clearing Data

```bash
# Clear conversation history
Remove-Item -Recurse -Force data/

# Clear semantic memory
Remove-Item -Recurse -Force .claude/memory_v2/

# Clear all plans
Remove-Item -Recurse -Force .claude/plans/
```

---

## Network Security

### Outbound Connections

AgiCode makes outbound connections to:

| Service | Purpose | Required |
|---------|---------|----------|
| LLM API endpoints | Model inference | ✅ |
| DuckDuckGo HTML search | Web search | Optional |
| MCP servers | Tool execution | Optional |
| Any URL you specify | Web/browser tools | On demand |

### Proxy Support

Configure HTTP proxies via environment variables:

```bash
$env:HTTP_PROXY = "http://proxy:8080"
$env:HTTPS_PROXY = "http://proxy:8080"
```

---

## Reporting Vulnerabilities

If you discover a security vulnerability in AgiCode:

1. **Do NOT** open a public issue
2. Email details to the repository owner
3. Allow reasonable time for a fix before disclosure

---

## Security Checklist

- [ ] API keys stored in environment variables, not config.json
- [ ] `config.json` listed in `.gitignore`
- [ ] API key not visible in screenshots or logs
- [ ] Trusted MCP servers only
- [ ] Regular API key rotation
- [ ] Session monitoring active (GUI visible)
- [ ] `.gitignore` excludes sensitive files

---

*[Back to docs index](index.md)*
