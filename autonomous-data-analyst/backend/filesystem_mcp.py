"""Manual filesystem MCP client used to verify workspace read/write access."""

import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"


def prepare_workspace():
    """Create the directories exposed by the standalone filesystem check."""
    for folder in ("files", "analyses", "charts", "research", "reports"):
        (WORKSPACE_DIR / folder).mkdir(parents=True, exist_ok=True)


def build_filesystem_server():
    """Build the stdio configuration for the generic filesystem MCP server."""
    return StdioServerParameters(
        command="npx.cmd" if os.name == "nt" else "npx",
        args=[
            "-y",
            "@modelcontextprotocol/server-filesystem",
            str(WORKSPACE_DIR),
        ],
        env=os.environ.copy(),
    )


async def test_filesystem():
    """Connect to MCP, write a test file, and read it back."""
    # This is an executable integration check, not part of the main API path.
    prepare_workspace()
    server_params = build_filesystem_server()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            print("[FILESYSTEM] Available tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}")

            result = await session.call_tool(
                "write_file",
                {
                    "path": "analyses/test_analysis.txt",
                    "content": "Filesystem MCP test successful.",
                },
            )

            print("\n[WRITE RESULT]")
            print(result)

            result = await session.call_tool(
                "read_text_file",
                {
                    "path": "analyses/test_analysis.txt",
                },
            )

            print("\n[READ RESULT]")
            print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_filesystem())