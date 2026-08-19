import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


server = StdioServerParameters(
    command="python",
    args=[
        "-m",
        "servers.filesystem.server"
    ],
)


async def main():

    async with stdio_client(server) as (read, write):

        async with ClientSession(read, write) as session:

            print("Connected to server")

            await session.initialize()

            print("Server Initialized")

            tools = await session.list_tools()

            print("\nAvailable Tools\n")

            for tool in tools.tools:
                print(tool.name)
            print("\nCalling create_file...\n")
            while True:

                filename = input("\nEnter filename (or exit): ")

                if filename.lower() == "exit":
                    break

                result = await session.call_tool(
                    "create_file_tool",
                    {
                        "filename": filename
                    }
                )

                print(result)


if __name__ == "__main__":
    asyncio.run(main())