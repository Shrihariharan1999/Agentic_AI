# test_manager.py

import asyncio

from mcp_client.manager import MCPManager


async def main():

    manager = MCPManager()

    await manager.connect()

    tools = await manager.list_tools()

    print("\n========== AVAILABLE TOOLS ==========\n")

    for server_name, tool_list in tools.items():

        print(f"Server : {server_name}")

        for tool in tool_list:

            print(f"  {tool.name}")

            print(f"    Description : {tool.description}")

            print(f"    Input Schema : {tool.inputSchema}")

            print()

    await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())