import asyncio

from graph.graph_builder import graph
from langchain_core.messages import HumanMessage
from services.mcp_service import shutdown_manager


async def main():
    state = {
        "messages": []
    }

    print("=" * 50)
    print("AI Software Engineer")
    print("=" * 50)

    try:
        while True:
            user_input = input("\nYou : ")

            if user_input.lower() in ["exit", "quit"]:
                break

            state["messages"].append(HumanMessage(content=user_input))
            state = await graph.ainvoke(state)
            print("\nAI :", state["messages"][-1].content)
    finally:
        await shutdown_manager()


if __name__ == "__main__":
    asyncio.run(main())