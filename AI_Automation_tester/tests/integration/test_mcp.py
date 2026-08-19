import pytest

from app.mcp.manager import mcp_manager


@pytest.mark.asyncio
async def test_browser_mcp_tools():
    tools = await mcp_manager.get_tools()

    assert tools
    assert len(tools) > 0

    print("\nAvailable Browser MCP tools:")

    for tool in tools:
        print(f"- {tool.name}")