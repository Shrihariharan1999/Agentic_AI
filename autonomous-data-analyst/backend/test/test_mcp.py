"""List custom MCP tools and verify a basic document write operation."""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    """Connect to the custom MCP server and test document writing."""
    # The MCP server is launched as a child process and communicates over
    # standard input/output rather than through the HTTP API.
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            print("Available MCP tools:")

            for tool in tools.tools:
                print(f"- {tool.name}")

            result = await session.call_tool(
    "write_document",
    {
        "session_id": "test-session",
        "document_name": "MCP Test Report",
        "document_format": "md",
        "content": "# MCP Test Report\n\nThis document was created by the MCP server.",
        "images": [],
        "validation_status": "PASS",
    },
)

            print("\nDocument result:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())