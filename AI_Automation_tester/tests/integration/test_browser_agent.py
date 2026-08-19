import pytest

from app.agents.browser_agent import create_browser_agent
from app.mcp.manager import mcp_manager


@pytest.mark.asyncio
async def test_browser_agent():
    tools = await mcp_manager.get_tools()

    agent = create_browser_agent(tools)

    result = await agent.ainvoke({
        "messages": [
            {
                "role": "user",
                "content": "Who won IPL 2026 title?",
            }
        ]
    })

    print("\nAll messages:")

    for message in result["messages"]:
        print("\nMessage type:", type(message).__name__)
        print("Content:", message.content)
        print("Tool calls:", getattr(message, "tool_calls", []))

    assert result["messages"]