import asyncio
from langchain_core.messages import HumanMessage
from services.agent_service import process

async def main():
    response = await process([
        HumanMessage(content="Create a file named demo.txt in the workspace with the content Hello from agentic AI.")
    ])
    print(response.content)

asyncio.run(main())
