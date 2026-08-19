import asyncio

from langchain_core.messages import HumanMessage

from services.llm_service import chat


async def main():

    response = await chat(
        [
            HumanMessage(
                content="capuccino is a type of coffee. What are the ingredients of a cappuccino? explain and write it in the .md format"
            )
        ]
    )

    print("=" * 60)
    print(response)
    print("=" * 60)

    print("\nTool Calls\n")

    print(response.tool_calls)


if __name__ == "__main__":
    asyncio.run(main())