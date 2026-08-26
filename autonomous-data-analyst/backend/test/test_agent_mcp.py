"""Exercise the Playwright MCP workflow with navigation-before-snapshot rules."""

import asyncio
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools


load_dotenv()


MAX_TOOL_CALLS = 4

PLAYWRIGHT_TOOLS = {
    "browser_navigate",
    "browser_snapshot",
}


def build_mcp_client():
    """Create the Playwright MCP client used by this integration test."""
    return MultiServerMCPClient(
        {
            "playwright": {
                "transport": "stdio",
                "command": "npx.cmd" if os.name == "nt" else "npx",
                "args": [
                    "-y",
                    "@playwright/mcp@latest",
                ],
                "env": os.environ.copy(),
            }
        },
        tool_name_prefix=False,
        handle_tool_errors=True,
    )


async def run_test():
    """Verify the agent navigates once before collecting browser evidence."""
    client = build_mcp_client()

    async with client.session("playwright") as session:
        tools = await load_mcp_tools(session)

        selected_tools = [
            tool
            for tool in tools
            if tool.name in PLAYWRIGHT_TOOLS
        ]

        print("[TEST] Stateful tools exposed to Gemini:")

        for tool in selected_tools:
            print(f"  - {tool.name}")

        if not selected_tools:
            print("[ERROR] No required Playwright tools were loaded.")
            print("[AVAILABLE TOOLS]")
            for tool in tools:
                print(f"  - {tool.name}")
            return

        tool_map = {
            tool.name: tool
            for tool in selected_tools
        }

        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite"
        )

        llm_with_tools = llm.bind_tools(selected_tools)

        messages = [
            SystemMessage(
                content="""
You are a controlled web research agent.

Task:
Find who won IPL 2026.

Mandatory workflow:
1. Call browser_navigate exactly once.
2. Navigate to a useful web page containing the IPL 2026 result.
3. After navigation, call browser_snapshot.
4. Use the snapshot as the evidence.
5. Do not call browser_navigate again.
6. Do not answer from memory.
7. Use only browser_navigate and browser_snapshot.
8. Stop after obtaining the snapshot evidence.
"""
            ),
            HumanMessage(
                content="Who won IPL 2026?"
            ),
        ]

        tool_call_count = 0
        navigation_done = False
        snapshot_done = False

        while tool_call_count < MAX_TOOL_CALLS:
            # Keep the loop bounded so a model that repeats a tool call cannot
            # run the integration test indefinitely.
            print(f"\n[LLM] Playwright test agent: invocation {tool_call_count + 1}, tool calls used: {tool_call_count}/{MAX_TOOL_CALLS}")

            response = llm_with_tools.invoke(messages)
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", [])

            if not tool_calls:
                print("\n[FINAL ANSWER]")
                print(response.content)
                return

            for call in tool_calls:
                tool_name = call["name"]
                tool_args = call.get("args", {})

                print(f"\n[TOOL] {tool_name}")
                print(f"[ARGS] {tool_args}")

                if tool_name not in tool_map:
                    tool_result = f"Tool '{tool_name}' is not allowed."
                    print("[BLOCKED] Tool not allowed.")

                elif tool_name == "browser_navigate" and navigation_done:
                    tool_result = (
                        "Navigation has already been completed. "
                        "Use browser_snapshot now."
                    )
                    print("[BLOCKED] Duplicate navigation.")

                elif tool_name == "browser_snapshot" and not navigation_done:
                    tool_result = (
                        "Navigation must happen before browser_snapshot."
                    )
                    print("[BLOCKED] Snapshot before navigation.")

                else:
                    try:
                        tool_result = await tool_map[tool_name].ainvoke(
                            tool_args
                        )

                        if tool_name == "browser_navigate":
                            navigation_done = True

                        elif tool_name == "browser_snapshot":
                            snapshot_done = True

                    except Exception as exc:
                        tool_result = f"Tool execution failed: {exc}"

                print("\n[RESULT]")
                print(str(tool_result)[:8000])

                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=call["id"],
                    )
                )

                tool_call_count += 1

                print(
                    f"[TOOL CALLS] "
                    f"{tool_call_count}/{MAX_TOOL_CALLS}"
                )

                if snapshot_done:
                    break

                if tool_call_count >= MAX_TOOL_CALLS:
                    break

            if snapshot_done:
                print("\n[FINAL] Snapshot obtained. Asking Gemini for final answer.")

                print("[LLM] Playwright test verifier: answering from browser evidence")
                final_response = llm.invoke([
                    *messages,
                    SystemMessage(
                        content="""
Answer the user's question using only the browser evidence
contained in the conversation.

Do not use prior model knowledge.
Do not browse again.
Give a concise answer and mention the source/page evidence.
"""
                    ),
                ])

                print("\n[FINAL ANSWER]")
                print(final_response.content)
                return

        print("\n[TEST] Maximum tool-call limit reached.")


if __name__ == "__main__":
    asyncio.run(run_test())