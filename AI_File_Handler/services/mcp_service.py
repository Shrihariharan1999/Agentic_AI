from mcp_client.manager import MCPManager
from services.mcp_tools import reset_tools

_manager = None


async def _get_manager():
    global _manager

    if _manager is None:
        _manager = MCPManager()
        await _manager.connect()

    return _manager


async def shutdown_manager():
    global _manager

    if _manager is None:
        return

    try:
        await _manager.disconnect()
    finally:
        _manager = None
        await reset_tools()


async def call_tool(tool_name, arguments):
    manager = await _get_manager()

    return await manager.call_tool(
        server="filesystem",
        tool=tool_name,
        arguments=arguments
    )