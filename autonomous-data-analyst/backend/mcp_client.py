"""Connect the analyst to the custom and sandboxed filesystem MCP servers."""

import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


BASE_DIR = Path(__file__).resolve().parent.parent
SANDBOX_DIR = BASE_DIR / "sandbox"
WORKSPACE_DIR = BASE_DIR / "workspace"
CUSTOM_SERVER = BASE_DIR / "backend" / "mcp_server.py"

SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def build_mcp_connections():
    """Describe the custom and sandboxed MCP servers for the agent client."""
    # Keep the generic filesystem MCP server inside sandbox/; report writing
    # uses the application's controlled workspace writer instead.
    return {
        "custom": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(CUSTOM_SERVER)],
            "env": os.environ.copy(),
        },
        "sandbox_filesystem": {
            "transport": "stdio",
            "command": "npx.cmd" if os.name == "nt" else "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(SANDBOX_DIR),
            ],
            "env": os.environ.copy(),
        },
        "workspace_filesystem": {
            "transport": "stdio",
            "command": "npx.cmd" if os.name == "nt" else "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(WORKSPACE_DIR),
            ],
            "env": os.environ.copy(),
        },
    }


async def load_mcp_tools():
    """Connect to both MCP servers and return the client plus discovered tools."""
    client = MultiServerMCPClient(
        build_mcp_connections(),
        tool_name_prefix=True,
        handle_tool_errors=True,
    )

    tools = await client.get_tools()

    print(f"[MCP] Loaded {len(tools)} tools")

    for tool in tools:
        print(f"  - {tool.name}")

    return client, tools