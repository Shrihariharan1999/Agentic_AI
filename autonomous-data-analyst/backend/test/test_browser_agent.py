"""Run a manual web-research smoke test and print structured evidence."""

import asyncio
import json

from browser_agent import BrowserResearchAgent


async def main():
    """Run a manual search smoke test and print the structured result."""
    agent = BrowserResearchAgent()
    result = await agent.research("Who won IPL 2026?")
    print("\n[RESULT]")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())