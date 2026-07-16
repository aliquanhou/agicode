# Development Guide

> **Extend, customize, and contribute to AgiCode** — tool creation, testing, and contribution guidelines.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Creating a New Tool](#2-creating-a-new-tool)
3. [Creating a Plugin](#3-creating-a-plugin)
4. [Adding a New LLM Provider](#4-adding-a-new-llm-provider)
5. [Testing](#5-testing)
6. [Contribution Guidelines](#6-contribution-guidelines)
7. [Code Style](#7-code-style)

---

## 1. Project Structure

```
AgiCode/
├── agent/                          # Core agent package
│   ├── __init__.py                 # Package init, public API
│   ├── __main__.py                 # CLI entry point
│   ├── core.py                     # Agent main loop
│   ├── transcript.py               # Event bus
│   ├── workflow.py                 # State machine
│   ├── providers.py                # LLM provider abstraction
│   ├── prompt.py                   # System prompt builder
│   ├── session.py                  # Session state management
│   ├── context.py                  # Context compression
│   ├── tools.py                    # Tool registry + dispatch
│   ├── tools_*.py                  # Tool implementations
│   ├── tools_core.py               # Backward compatibility layer
│   ├── mcp/client.py               # MCP stdio client
│   ├── tools_mcp.py                # MCP tool integration
│   ├── app.py                      # GUI application
│   ├── app_dialogs.py              # GUI dialogs
│   ├── agent_loader.py             # Agent definition loader
│   ├── agents/                     # Agent definitions (*.md)
│   ├── plugins/                    # Plugin tools
│   ├── memory.py                   # Persistent memory
│   ├── memory_v2.py                # Semantic memory (ChromaDB)
│   ├── file_cache.py               # MMAP file cache
│   ├── speculative.py              # Speculative execution
│   ├── streaming_parser.py         # Streaming parser
│   ├── retry.py                    # Retry with backoff
│   ├── router.py                   # Model router
│   ├── researcher.py               # Deep research engine
│   ├── reviewer.py                 # Code review engine
│   ├── project_map.py              # Project mapping
│   ├── mcpserver.py                # MCP server management
│   ├── scheduler.py                # Cron scheduler
│   ├── watcher.py                  # File/process watcher
│   ├── build_patterns/             # Build error patterns
│   └── _encoding.py                # Encoding utilities
├── tests/                          # Test suite (211+ tests)
├── docs/                           # Documentation
├── main.py                         # CLI entry (standalone)
├── launch_gui.py                   # GUI launcher
├── config.json                     # Configuration
└── pyproject.toml                  # Project metadata
```

---

## 2. Creating a New Tool

### Method A: Auto-registered Module (Recommended)

Create a function with `_handle_` prefix in any `agent/tools_*.py` module:

```python
# agent/tools_myfeature.py
def _handle_my_tool(param1: str = "", param2: int = 0) -> str:
    """My custom tool description.

    Args:
        param1: First parameter description
        param2: Second parameter description

    Returns:
        Result string
    """
    if not param1:
        return "[错误] my_tool 需要 param1 参数"

    try:
        # Your tool logic here
        result = do_something(param1, param2)
        return f"[结果] {result}"
    except Exception as e:
        return f"[错误] 操作失败: {e}"
```

Then register the module in `agent/tools.py`:

```python
def _register_builtins():
    tool_modules = [
        # ... existing modules ...
        "agent.tools_myfeature",  # ← Add your module here
    ]
```

The tool is automatically registered as "my_tool" with parameters inferred from type annotations.

### Method B: Manual Registration

```python
from agent.tools import register_tool

def my_handler(**params) -> str:
    file_path = params.get("file_path", "")
    # ... implementation ...
    return "result"

register_tool(
    name="my_tool",
    handler=my_handler,
    description="Description visible to the LLM",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file",
            },
        },
        "required": ["file_path"],
    },
)
```

### Tool Development Checklist

- [ ] Function signature has type annotations
- [ ] Returns a string (not an object, not None)
- [ ] Error handled with explicit return message
- [ ] All required parameters checked at the start
- [ ] Added registration to `_register_builtins()` (if auto-module)
- [ ] Test added to `tests/`

---

## 3. Creating a Plugin

Create a plugin in `agent/plugins/`:

```python
# agent/plugins/my_plugin.py
from agent.tools import register_tool

def register() -> dict:
    """Register this plugin with the tool system.

    Returns:
        dict with keys: name, handler, description, input_schema
    """
    return {
        "name": "my_plugin_tool",
        "handler": my_handler,
        "description": "My plugin tool description",
        "input_schema": {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
            },
        },
    }

def my_handler(params: dict) -> str:
    """Plugin tool handler (receives dict)."""
    param1 = params.get("param1", "")
    return f"处理结果: {param1}"
```

---

## 4. Adding a New LLM Provider

### Step 1: Create Provider Class

```python
# agent/providers_myprovider.py
from .providers import LLMProvider

class MyProvider(LLMProvider):
    models = ["my-model-1", "my-model-2"]
    default_model = "my-model-1"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.environ.get("MY_API_KEY", "")
        self.model = config.get("model", self.default_model)
        self.base_url = config.get("base_url", "https://api.myprovider.com/v1")

    def complete(self, system, messages, tools=None, max_tokens=8192, temperature=0.0):
        # Implementation
        return {"content": "...", "tool_calls": [...]}

    def stream_complete(self, system, messages, tools=None,
                        max_tokens=8192, temperature=0.0,
                        on_text=None, on_tool_start=None, on_thinking=None):
        # Streaming implementation
        return {"content": "...", "tool_calls": [...]}
```

### Step 2: Register in Factory

```python
# agent/providers.py — in create_llm_provider()
elif "myprovider" in model.lower():
    from .providers_myprovider import MyProvider
    return MyProvider({**config, "model": model})
```

---

## 5. Testing

### Running Tests

```bash
# Full test suite
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_tools_file.py -v

# Specific test
python -m pytest tests/test_tools_file.py::TestFileTools::test_read -v

# With coverage
python -m pytest tests/ --cov=agent --cov-report=term
```

### Writing Tests

```python
# tests/test_myfeature.py
from agent.tools import get_tool, execute_tool, register_tool

class TestMyTool:
    def test_registered(self):
        """Verify the tool is registered."""
        tool = get_tool("my_tool")
        assert tool is not None
        assert tool["name"] == "my_tool"

    def test_basic_operation(self):
        """Test basic functionality."""
        result = execute_tool("my_tool", {"param1": "test"})
        assert "结果" in result

    def test_missing_param(self):
        """Test error handling for missing params."""
        result = execute_tool("my_tool", {})
        assert "错误" in result

    def test_edge_case(self):
        """Test edge case."""
        result = execute_tool("my_tool", {"param1": "", "param2": "0"})
        assert isinstance(result, str)
```

---

## 6. Contribution Guidelines

### Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Write code and tests
4. Ensure 211+ tests pass
5. Submit a Pull Request

### Code Review Process

All contributions go through review:
1. Automated tests must pass
2. Code style must match existing patterns
3. New features must include tests
4. Documentation must be updated

### What We Welcome

- New tool implementations
- Additional LLM providers
- Bug fixes and edge cases
- Performance optimizations
- Documentation improvements
- Test coverage expansions

---

## 7. Code Style

### Python

- PEP 8 compliant
- Type hints for all function signatures
- Descriptive docstrings for public functions
- Error messages returned as strings, never raised as exceptions
- All user-facing strings in Chinese (for Chinese users) or English

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Tool handler | `_handle_<tool_name>` | `_handle_read` |
| Tool parameter | snake_case | `file_path` |
| Internal function | `_` prefix | `_coerce_params` |
| Class | PascalCase | `Agent`, `SessionState` |
| Module | snake_case | `tools_file.py` |

### Error Handling Pattern

```python
def _handle_something(param: str = "") -> str:
    if not param:
        return "[错误] something 需要 param 参数"
    try:
        # Implementation
        return f"[成功] 操作完成: {result}"
    except Exception as e:
        return f"[错误] 操作失败: {e}"
```

### Commit Message Format

```
feat(tools): add new browser screenshot tool
fix(core): handle empty tool_calls gracefully
docs(architecture): update data flow diagram
test(tools): add tests for file operations
refactor(session): simplify state management
```

---

*[Back to docs index](index.md)*
