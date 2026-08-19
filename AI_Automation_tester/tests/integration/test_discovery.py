import pytest

from app.agents.discovery import create_discovery_agent
from app.mcp.manager import mcp_manager
from app.services.discovery_extractor import DiscoveryExtractor


@pytest.mark.asyncio
async def test_discovery_agent():
    async with mcp_manager.browser_session() as tools:
        agent = create_discovery_agent(tools)

        result = await agent.ainvoke({
            "messages": [
                {
                    "role": "user",
                    "content": "Discover the website https://amudham-ayurveda-clinic.vercel.app/",
                }
            ]
        })

        print("\nDiscovery messages:")

        for message in result["messages"]:
            print("\nMessage type:", type(message).__name__)
            print("Content:", message.content)
            print("Tool calls:", getattr(message, "tool_calls", []))

        browser_evidence = "\n".join(
            str(message.content)
            for message in result["messages"]
            if message.content
        )

        extractor = DiscoveryExtractor()

        website_map = extractor.extract(browser_evidence)

        print("\nWebsiteMap:")
        print(website_map.model_dump_json(indent=2))

        assert website_map.website.url