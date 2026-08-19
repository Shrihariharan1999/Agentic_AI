import asyncio
import json

from services.mcp_tools import get_tools


async def main():

    tools = await get_tools()

    for tool in tools:

        print("=" * 80)
        print("Tool Name:")
        print(tool.name)

        print("\nDescription:")
        print(tool.description)

        print("\nArgs Schema Type:")
        print(type(tool.args_schema))

        print("\nArgs Schema:")
        print(json.dumps(tool.args_schema, indent=4))

        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())