# MCP Integration

> **Connect any MCP server** — tools auto-register and become available like built-in tools.

---

## What is MCP?

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io) is an open standard that enables AI agents to connect with external tools and services. AgiCode implements a **stdio-based MCP client** that:

1. Launches MCP server processes
2. Discovers available tools via `tools/list`
3. Auto-registers them as callable tools
4. Routes tool calls through `tools/call`

---

## Quick Start

### Auto-connect via config.json

```json
{
  "mcp_servers": [
    {
      "name": "playwright",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-playwright"]
    },
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    }
  ]
}
```

AgiCode auto-connects all configured servers on startup.

### Manual Connect at Runtime

```
mcp action=connect server=playwright command=npx args="[\"-y\", \"@anthropic/mcp-playwright\"]"
```

---

## Command Reference

### `mcp` Tool

| Action | Description | Required Parameters |
|--------|-------------|-------------------|
| `list` | List connected MCP servers | — |
| `connect` | Connect a new MCP server | `server`, `command` |
| `disconnect` | Disconnect a server | `server` |
| `call` | Call a tool directly | `server`, `tool_name` + kwargs |

### Examples

```bash
# List connected servers
mcp action=list

# Connect a server
mcp action=connect server=playwright command=npx args="[\"-y\", \"@anthropic/mcp-playwright\"]"

# Disconnect
mcp action=disconnect server=playwright

# Call a tool directly (bypass registration)
mcp action=call server=filesystem tool_name=read path="/tmp/test.txt"
```

---

## How MCP Tools Work

### Auto-registration

When an MCP server connects, AgiCode:

1. Launches the server process with stdio transport
2. Sends `initialize` JSON-RPC request
3. Calls `tools/list` to discover available tools
4. Registers each tool as `mcp__{server}__{tool}`

```
Connection Flow:

AgiCode                     MCP Server
   │                            │
   ├── initialize ──────────────┤
   │                            ├── Start up
   │◄─── initialized ──────────┤
   │                            │
   ├── tools/list ──────────────┤
   │◄─── tools: [tool1, tool2] ─┤
   │                            │
   ├── Register mcp__server__tool1
   ├── Register mcp__server__tool2
   │                            │
   │◄── Ready ──────────────────┤
```

### Tool Naming

Registered tools use the pattern: `mcp__{server_name}__{tool_name}`

```
Server: "playwright" → Tool: "mcp__playwright__screenshot"
Server: "filesystem" → Tool: "mcp__filesystem__read"
```

### Usage

Once registered, MCP tools work like any built-in tool — the LLM can call them directly:

```
# LLM can use MCP tools seamlessly
browser action=open url="https://example.com"     # built-in
mcp__playwright__screenshot                        # auto-registered MCP tool
```

---

## Protocol Details

AgiCode implements JSON-RPC 2.0 over stdio:

### Initialize

```json
→ {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"0.1.0","capabilities":{}}}
← {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"0.1.0","capabilities":{...}}}
```

### List Tools

```json
→ {"jsonrpc":"2.0","id":2,"method":"tools/list"}
← {"jsonrpc":"2.0","id":2,"result":{"tools":[
    {"name":"read","description":"Read file","inputSchema":{"type":"object","properties":{...}}},
    {"name":"write","description":"Write file","inputSchema":{...}}
]}}
```

### Call Tool

```json
→ {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read","arguments":{"path":"/tmp/test.txt"}}}
← {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"file content..."}]}}
```

---

## Supported MCP Servers

### Official Servers

| Server | Description | Install |
|--------|-------------|---------|
| [@anthropic/mcp-playwright](https://github.com/anthropics/mcp-playwright) | Browser automation | `npx -y @anthropic/mcp-playwright` |
| [@modelcontextprotocol/server-filesystem](https://github.com/modelcontextprotocol/servers) | Filesystem access | `npx -y @modelcontextprotocol/server-filesystem .` |
| [@modelcontextprotocol/server-github](https://github.com/modelcontextprotocol/servers) | GitHub API | `npx -y @modelcontextprotocol/server-github` |
| [@modelcontextprotocol/server-postgres](https://github.com/modelcontextprotocol/servers) | PostgreSQL | `npx -y @modelcontextprotocol/server-postgres` |
| [@modelcontextprotocol/server-sqlite](https://github.com/modelcontextprotocol/servers) | SQLite | `npx -y @modelcontextprotocol/server-sqlite` |

### Custom Servers

You can connect any stdio-based MCP server:

```json
{
  "mcp_servers": [
    {
      "name": "my-custom-server",
      "command": "python",
      "args": ["path/to/mcp_server.py"]
    }
  ]
}
```

---

## Implementation

### Client (`agent/mcp/client.py`)

```python
class McpServer:
    def __init__(self, name, command, args=None, env=None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}

    def connect(self) -> bool:
        """Start subprocess and send initialize."""
        ...

    def discover_tools(self) -> list[dict]:
        """Call tools/list to discover available tools."""
        ...

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool and return result text."""
        ...
```

### Tool Bridge (`agent/tools_mcp.py`)

```python
def _make_mcp_handler(server_name, tool_name):
    """Create a handler function for an MCP tool."""
    def handler(**params) -> str:
        srv = get_server(server_name)
        return srv.call_tool(tool_name, params)
    return handler
```

---

## Auto-connect Flow

On startup, `init_tools()` calls `auto_connect_servers(config)`:

```python
def auto_connect_servers(config):
    servers = config.get("mcp_servers", [])
    for svr in servers:
        _connect_mcp(
            name=svr["name"],
            command=svr["command"],
            args=svr.get("args", []),
        )
```

Each server is connected in sequence; individual failures are logged but don't block startup.

---

*[Back to docs index](index.md)*
