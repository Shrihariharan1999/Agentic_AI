from graph.state import AgentState

from langchain_core.messages import AIMessage

from services.agent_service import process


async def chatbot_node(state: AgentState):
    response = await process(state["messages"])

    return {
        "messages": [
            AIMessage(content=response.content)
        ]
    }