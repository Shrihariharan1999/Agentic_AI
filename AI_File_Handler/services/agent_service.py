from langchain_core.messages import AIMessage, ToolMessage

from services.llm_service import chat
from services.mcp_service import call_tool


def _get_tool_call_value(tool_call, field_name):
    if isinstance(tool_call, dict):
        return tool_call.get(field_name)

    if hasattr(tool_call, field_name):
        return getattr(tool_call, field_name)

    return None


async def process(messages):
    """
    Main Agent Orchestrator

    Flow

    User
        ↓
    LLM
        ↓
    Tool Required?
      Yes / No
        ↓
    MCP
        ↓
    LLM
        ↓
    Final Response
    """

    history = list(messages)

    while True:
        response = await chat(history)

        if not getattr(response, "tool_calls", None):
            return response

        tool_messages = []

        for tool_call in response.tool_calls:
            tool_name = _get_tool_call_value(tool_call, "name")
            tool_args = _get_tool_call_value(tool_call, "args") or {}
            tool_call_id = _get_tool_call_value(tool_call, "id")

            tool_result = await call_tool(
                tool_name=tool_name,
                arguments=tool_args
            )

            tool_messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call_id
                )
            )

        history = history + [
            AIMessage(
                content=response.content,
                tool_calls=response.tool_calls
            ),
            *tool_messages
        ]