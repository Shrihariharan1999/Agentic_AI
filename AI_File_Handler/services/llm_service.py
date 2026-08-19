from config import llm
from prompts.system_prompt import SYSTEM_PROMPT

from langchain_core.messages import SystemMessage

from services.mcp_tools import get_tools


async def chat(messages):

    tools = await get_tools()

    tool_llm = llm.bind_tools(tools)

    all_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *messages
    ]

    response = await tool_llm.ainvoke(all_messages)

    return response


async def stream_chat(messages):

    tools = await get_tools()

    tool_llm = llm.bind_tools(tools)

    all_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *messages
    ]

    async for chunk in tool_llm.astream(all_messages):
        yield chunk